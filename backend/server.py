"""JurnalMap FastAPI backend — single entry point with all routes."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# IMPORTANT: load .env BEFORE importing any app.* module so that
# os.environ.get(...) calls at module-import time see the right values.
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import logging
import uuid
from typing import List, Optional

import aiofiles
from fastapi import (
    FastAPI,
    APIRouter,
    BackgroundTasks,
    UploadFile,
    File,
    HTTPException,
    Body,
)
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.middleware.cors import CORSMiddleware

from app.models.schemas import (
    Project,
    ProjectCreate,
    DocumentMeta,
    EvidenceResponse,
    EvidenceItem,
    OutlierResponse,
    MatrixResponse,
    MatrixRow,
    MatrixCell,
    AskRequest,
    AskResponse,
    Citation,
    Settings,
    PERSONAS,
    MATRIX_METHODS,
    DocumentTitleUpdate,
    new_uid,
    utcnow_iso,
)
from app.services.document_processor import process_document, regenerate_summary
from app.services.evidence_service import find_evidence
from app.services.outlier_service import compute_outliers
from app.services.matrix_service import extract_row, fields_for
from app.services.qa_service import answer_question
from app.services.synthesis_service import generate_subchapter, find_supporting_source, CITATION_FORMATS
from app.services.llm import split_provider_model, emergent_key, default_model, LLMJSONError


UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", str(ROOT_DIR / "uploads")))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="JurnalMap API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("jurnalmap")

_IEEE_LABEL_RE = __import__("re").compile(r"^\[(\d+)\]$")


# ---- Helpers ----
def _strip_mongo(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


async def _project_or_404(project_id: str) -> dict:
    p = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Project not found")
    return p


async def _document_or_404(document_id: str) -> dict:
    d = await db.documents.find_one({"id": document_id}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Document not found")
    return d


# ---- Health ----
@api.get("/")
async def root():
    return {"app": "JurnalMap", "status": "ok"}


# ---- Projects ----
@api.post("/projects", response_model=Project)
async def create_project(payload: ProjectCreate):
    p = Project(name=payload.name.strip() or "Untitled project", description=payload.description.strip())
    await db.projects.insert_one(p.model_dump())
    return p


@api.get("/projects", response_model=List[Project])
async def list_projects():
    rows = await db.projects.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    # attach document_count
    for r in rows:
        r["document_count"] = await db.documents.count_documents({"project_id": r["id"]})
    return [Project(**r) for r in rows]


@api.get("/projects/{project_id}", response_model=Project)
async def get_project(project_id: str):
    p = await _project_or_404(project_id)
    p["document_count"] = await db.documents.count_documents({"project_id": project_id})
    return Project(**p)


@api.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    await _project_or_404(project_id)
    # cascade: documents, sentences, claims
    docs = await db.documents.find({"project_id": project_id}, {"_id": 0, "id": 1}).to_list(1000)
    doc_ids = [d["id"] for d in docs]
    if doc_ids:
        await db.sentences.delete_many({"document_id": {"$in": doc_ids}})
        await db.claims.delete_many({"document_id": {"$in": doc_ids}})
        await db.matrix_cache.delete_many({"document_id": {"$in": doc_ids}})
        # remove files
        for did in doc_ids:
            fp = UPLOAD_DIR / f"{did}.pdf"
            if fp.exists():
                try:
                    fp.unlink()
                except OSError:
                    pass
    await db.documents.delete_many({"project_id": project_id})
    await db.workspace_outlines.delete_many({"project_id": project_id})
    await db.workspace_contents.delete_many({"project_id": project_id})
    await db.projects.delete_one({"id": project_id})
    return {"deleted": True}


# ---- Documents ----
@api.get("/projects/{project_id}/documents", response_model=List[DocumentMeta])
async def list_documents(project_id: str):
    await _project_or_404(project_id)
    rows = await db.documents.find({"project_id": project_id}, {"_id": 0}).sort("uploaded_at", -1).to_list(500)
    return [DocumentMeta(**r) for r in rows]


@api.post("/projects/{project_id}/documents", response_model=DocumentMeta)
async def upload_document(
    project_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    await _project_or_404(project_id)
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted")

    doc_id = new_uid()
    dest = UPLOAD_DIR / f"{doc_id}.pdf"
    async with aiofiles.open(dest, "wb") as out:
        while True:
            chunk = await file.read(1 << 20)
            if not chunk:
                break
            await out.write(chunk)

    meta = DocumentMeta(id=doc_id, project_id=project_id, filename=file.filename, status="processing")
    await db.documents.insert_one(meta.model_dump())

    settings = await _load_settings()
    model_id = settings.get("default_model") or default_model()
    provider, model_id = split_provider_model(model_id, settings)
    background_tasks.add_task(
        process_document,
        db,
        doc_id,
        str(dest),
        user_settings=settings,
        provider=provider,
        model=model_id,
    )
    return meta


@api.get("/documents/{document_id}", response_model=DocumentMeta)
async def get_document(document_id: str):
    d = await _document_or_404(document_id)
    return DocumentMeta(**d)


@api.patch("/documents/{document_id}", response_model=DocumentMeta)
async def update_document(document_id: str, payload: DocumentTitleUpdate):
    """Update editable document fields. Currently: title only."""
    d = await _document_or_404(document_id)
    new_title = (payload.title or "").strip()
    if not new_title:
        raise HTTPException(400, "title must not be empty")
    if len(new_title) > 500:
        new_title = new_title[:500]
    await db.documents.update_one({"id": document_id}, {"$set": {"title": new_title}})
    # Also refresh the cached title on any matrix cache rows for this doc so the
    # comparison table reflects the new label without re-running the LLM.
    await db.matrix_cache.update_many({"document_id": document_id}, {"$set": {"title": new_title}})
    d["title"] = new_title
    return DocumentMeta(**d)


@api.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    d = await _document_or_404(document_id)
    await db.sentences.delete_many({"document_id": document_id})
    await db.claims.delete_many({"document_id": document_id})
    await db.matrix_cache.delete_many({"document_id": document_id})
    await db.documents.delete_one({"id": document_id})
    fp = UPLOAD_DIR / f"{document_id}.pdf"
    if fp.exists():
        try:
            fp.unlink()
        except OSError:
            pass
    return {"deleted": True, "id": d["id"]}


@api.get("/documents/{document_id}/pdf")
async def serve_pdf(document_id: str):
    await _document_or_404(document_id)
    fp = UPLOAD_DIR / f"{document_id}.pdf"
    if not fp.exists():
        raise HTTPException(404, "PDF file missing")
    return FileResponse(str(fp), media_type="application/pdf")


async def _load_settings() -> dict:
    """Load the singleton settings doc, falling back to defaults."""
    doc = await db.settings.find_one({"id": "singleton"}, {"_id": 0})
    if not doc:
        doc = Settings().model_dump()
    return doc


def _models_for(settings: dict) -> list[dict]:
    """Return the list of models the user can pick. Always include Emergent defaults."""
    models = []
    if emergent_key():
        models += [
            {"id": "gemini-3-flash-preview", "provider": "gemini", "label": "Gemini 3 Flash (Emergent)"},
            {"id": "gemini-2.5-pro", "provider": "gemini", "label": "Gemini 2.5 Pro (Emergent)"},
            {"id": "gpt-5.4-mini", "provider": "openai", "label": "GPT-5.4 Mini (Emergent)"},
            {"id": "claude-haiku-4-5", "provider": "anthropic", "label": "Claude Haiku 4.5 (Emergent)"},
        ]
    if settings.get("gemini_key"):
        models.append({"id": "gemini-3-flash-preview", "provider": "gemini", "label": "Gemini 3 Flash (Your key)"})
        models.append({"id": "gemini-2.5-pro", "provider": "gemini", "label": "Gemini 2.5 Pro (Your key)"})
    if settings.get("openai_key"):
        models.append({"id": "gpt-4o-mini", "provider": "openai", "label": "GPT-4o Mini (Your key)"})
        models.append({"id": "gpt-4o", "provider": "openai", "label": "GPT-4o (Your key)"})
    if settings.get("anthropic_key"):
        models.append({"id": "claude-sonnet-4-5", "provider": "anthropic", "label": "Claude Sonnet 4.5 (Your key)"})
    if settings.get("local_endpoint") and settings.get("local_model"):
        models.append({
            "id": settings["local_model"],
            "provider": "local",
            "label": f"{settings['local_model']} (Local)",
        })
    seen = set()
    out = []
    for m in models:
        key = (m["provider"], m["id"], m["label"])
        if key in seen:
            continue
        seen.add(key)
        out.append(m)
    return out


def _mask(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return value[:4] + "***" + value[-4:]


# ---- Settings ----
@api.get("/settings")
async def get_settings():
    s = await _load_settings()
    return {
        "theme": s.get("theme", "light"),
        "persona_id": s.get("persona_id", "akademisi_ketat"),
        "persona_custom": s.get("persona_custom", ""),
        "output_language": s.get("output_language", "en"),
        "ui_language": s.get("ui_language", "id"),
        "default_model": s.get("default_model") or default_model(),
        # masked keys for display
        "gemini_key_masked": _mask(s.get("gemini_key")),
        "openai_key_masked": _mask(s.get("openai_key")),
        "anthropic_key_masked": _mask(s.get("anthropic_key")),
        "has_gemini_key": bool(s.get("gemini_key")),
        "has_openai_key": bool(s.get("openai_key")),
        "has_anthropic_key": bool(s.get("anthropic_key")),
        # local endpoint
        "local_endpoint": s.get("local_endpoint", ""),
        "local_api_key_masked": _mask(s.get("local_api_key")) if s.get("local_api_key") and s.get("local_api_key") != "ollama" else "",
        "local_model": s.get("local_model", ""),
        "has_local": bool(s.get("local_endpoint") and s.get("local_model")),
        "personas": [{"id": k, "label": v["label"]} for k, v in PERSONAS.items()] + [{"id": "custom", "label": "Custom"}],
        "matrix_methods": [{"id": k, "label": v["label"]} for k, v in MATRIX_METHODS.items()],
        "available_models": _models_for(s),
    }


@api.put("/settings")
async def update_settings(payload: dict = Body(...)):
    s = await _load_settings()
    for k in (
        "theme", "persona_id", "persona_custom",
        "output_language", "ui_language",
        "default_model", "local_endpoint", "local_model",
    ):
        if k in payload and payload[k] is not None:
            s[k] = payload[k]
    for k in ("gemini_key", "openai_key", "anthropic_key", "local_api_key"):
        if k in payload:
            v = (payload.get(k) or "").strip()
            s[k] = v
    s["id"] = "singleton"
    await db.settings.update_one({"id": "singleton"}, {"$set": s}, upsert=True)
    return await get_settings()


@api.get("/documents/{document_id}/summary")
async def get_summary(document_id: str):
    d = await _document_or_404(document_id)
    claims = await db.claims.find({"document_id": document_id}, {"_id": 0}).sort("idx", 1).to_list(50)
    return {
        "document_id": document_id,
        "title": d.get("title") or d.get("filename"),
        "filename": d.get("filename"),
        "page_count": d.get("page_count", 0),
        "summary": d.get("summary") or "",
        "sections": d.get("sections") or {},
        "model_used": d.get("model_used"),
        "persona_used": d.get("persona_used"),
        "claims": claims,
        "status": d.get("status"),
        "error": d.get("error"),
    }


@api.get("/documents/{document_id}/status")
async def get_status(document_id: str):
    """Status endpoint that returns processing state + structured summary when ready."""
    d = await _document_or_404(document_id)
    claims = await db.claims.find({"document_id": document_id}, {"_id": 0}).sort("idx", 1).to_list(50)
    return {
        "id": document_id,
        "status": d.get("status"),
        "error": d.get("error"),
        "page_count": d.get("page_count", 0),
        "title": d.get("title") or d.get("filename"),
        "summary": {
            "overview": d.get("summary") or "",
            **(d.get("sections") or {}),
        } if d.get("status") == "ready" else None,
        "claims": claims if d.get("status") == "ready" else [],
        "model_used": d.get("model_used"),
        "persona_used": d.get("persona_used"),
    }


@api.post("/documents/{document_id}/summarize")
async def resummarize(document_id: str, model: Optional[str] = None, payload: dict = Body(default={})):
    """Regenerate summary with chosen model. Body may override persona for this single call."""
    await _document_or_404(document_id)
    settings = await _load_settings()
    # allow persona override for this single call
    if isinstance(payload, dict) and payload.get("persona_id"):
        settings = {**settings, "persona_id": payload["persona_id"]}
        if "persona_custom" in payload:
            settings["persona_custom"] = payload.get("persona_custom") or ""
    model_id = model or settings.get("default_model") or default_model()
    provider, model_id = split_provider_model(model_id, settings)
    try:
        await regenerate_summary(
            db,
            document_id,
            user_settings=settings,
            provider=provider,
            model=model_id,
        )
    except LLMJSONError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Model '{model_id}' returned malformed JSON. Please try another model. ({e})",
        )
    return await get_summary(document_id)


# ---- Evidence ----
@api.post("/claims/{claim_id}/evidence", response_model=EvidenceResponse)
async def evidence_for_claim(claim_id: str):
    claim = await db.claims.find_one({"id": claim_id}, {"_id": 0})
    if not claim:
        raise HTTPException(404, "Claim not found")
    sentences = await db.sentences.find({"document_id": claim["document_id"]}, {"_id": 0}).sort("idx", 1).to_list(5000)
    settings = await _load_settings()
    provider, model_id = split_provider_model(settings.get("default_model") or default_model(), settings)
    items = await find_evidence(
        claim["text"], sentences, k=5,
        user_settings=settings, provider=provider, model=model_id,
    )
    return EvidenceResponse(
        claim_id=claim_id,
        claim_text=claim["text"],
        items=[EvidenceItem(**i) for i in items],
    )


@api.post("/documents/{document_id}/section-evidence")
async def evidence_for_section(document_id: str, payload: dict = Body(...)):
    """Find evidence in a doc for arbitrary text (used by section-click in SummaryPanel)."""
    await _document_or_404(document_id)
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "text is required")
    sentences = await db.sentences.find({"document_id": document_id}, {"_id": 0}).sort("idx", 1).to_list(5000)
    settings = await _load_settings()
    provider, model_id = split_provider_model(settings.get("default_model") or default_model(), settings)
    items = await find_evidence(
        text, sentences, k=5,
        user_settings=settings, provider=provider, model=model_id,
    )
    return {"text": text, "items": items}


# ---- Outliers ----
@api.get("/projects/{project_id}/outliers", response_model=OutlierResponse)
async def project_outliers(project_id: str):
    await _project_or_404(project_id)
    docs = await db.documents.find({"project_id": project_id, "status": "ready"}, {"_id": 0}).to_list(500)
    payload = []
    for d in docs:
        sents = await db.sentences.find({"document_id": d["id"]}, {"_id": 0}).to_list(5000)
        payload.append({"id": d["id"], "title": d.get("title") or d.get("filename"), "sentences": sents})
    res = compute_outliers(payload)
    return OutlierResponse(**res)


# ---- Matrix ----
@api.post("/projects/{project_id}/matrix", response_model=MatrixResponse)
async def build_matrix(
    project_id: str,
    document_ids: Optional[List[str]] = Body(default=None, embed=True),
    refresh: bool = Body(default=False, embed=True),
    method: str = Body(default="default", embed=True),
):
    await _project_or_404(project_id)
    if method not in MATRIX_METHODS:
        method = "default"
    query = {"project_id": project_id, "status": "ready"}
    if document_ids:
        query["id"] = {"$in": document_ids}
    docs = await db.documents.find(query, {"_id": 0}).to_list(500)
    rows = []
    fields: List[str] = []
    for d in docs:
        title = d.get("title") or d.get("filename")
        cache_key = {"document_id": d["id"], "method": method}
        cached = None if refresh else await db.matrix_cache.find_one(cache_key, {"_id": 0})
        if cached and isinstance(cached.get("cells"), list) and cached["cells"]:
            row = {"document_id": d["id"], "title": title, "cells": cached["cells"]}
        else:
            sents = await db.sentences.find({"document_id": d["id"]}, {"_id": 0}).to_list(5000)
            settings_doc = await _load_settings()
            provider, model_id = split_provider_model(settings_doc.get("default_model") or default_model(), settings_doc)
            try:
                row = await extract_row(
                    d["id"], title, sents,
                    user_settings=settings_doc, provider=provider, model=model_id,
                    method=method,
                )
            except LLMJSONError as e:
                raise HTTPException(502, f"Model returned malformed JSON for matrix ({e})")
            # persist
            await db.matrix_cache.update_one(
                cache_key,
                {"$set": {
                    "document_id": d["id"],
                    "method": method,
                    "title": title,
                    "cells": row["cells"],
                    "cached_at": utcnow_iso(),
                }},
                upsert=True,
            )
        if not fields and row["cells"]:
            fields = [c["field"] for c in row["cells"]]
        rows.append(MatrixRow(document_id=row["document_id"], title=row["title"],
                              cells=[MatrixCell(**c) for c in row["cells"]]))
    if not fields:
        fields = fields_for(method)
    return MatrixResponse(fields=fields, rows=rows)


# ---- Ask Library ----
@api.post("/projects/{project_id}/ask", response_model=AskResponse)
async def ask_library(project_id: str, payload: AskRequest, model: Optional[str] = None):
    await _project_or_404(project_id)
    if not payload.question.strip():
        raise HTTPException(400, "question must not be empty")
    docs = await db.documents.find({"project_id": project_id, "status": "ready"}, {"_id": 0}).to_list(500)
    inputs = []
    for d in docs:
        sents = await db.sentences.find({"document_id": d["id"]}, {"_id": 0}).to_list(5000)
        inputs.append({"id": d["id"], "title": d.get("title") or d.get("filename"), "sentences": sents})
    settings = await _load_settings()
    model_id = model or settings.get("default_model") or default_model()
    provider, model_id = split_provider_model(model_id, settings)
    res = await answer_question(
        payload.question, inputs,
        user_settings=settings, provider=provider, model=model_id,
    )
    return AskResponse(
        question=res["question"],
        answer=res["answer"],
        citations=[Citation(**c) for c in res["citations"]],
        overall_tier=res["overall_tier"],
        model_used=res.get("model_used") or model_id,
        persona_used=res.get("persona_used") or settings.get("persona_id"),
    )


# ---- Workspace (Sintesis Berbasis Bukti) ----
@api.get("/projects/{project_id}/outline")
async def get_outline(project_id: str):
    await _project_or_404(project_id)
    doc = await db.workspace_outlines.find_one({"project_id": project_id}, {"_id": 0})
    if not doc:
        return {
            "project_id": project_id,
            "title": "",
            "chapters": [],
            "citation_format": "ieee",
            "exists": False,
        }
    doc["exists"] = True
    return doc


@api.post("/projects/{project_id}/outline")
async def save_outline(project_id: str, payload: dict = Body(...)):
    await _project_or_404(project_id)
    title = (payload.get("title") or "").strip() or "Untitled Paper"
    chapters = payload.get("chapters") or []
    citation_format = (payload.get("citation_format") or "ieee").lower()
    if citation_format not in CITATION_FORMATS:
        citation_format = "ieee"

    # Normalize: ensure ids exist
    norm_chapters = []
    for ch in chapters:
        if not isinstance(ch, dict):
            continue
        ch_id = ch.get("id") or new_uid()
        ch_title = (ch.get("title") or "Untitled chapter").strip()
        subs = []
        for sc in ch.get("subchapters") or []:
            if not isinstance(sc, dict):
                continue
            subs.append({
                "id": sc.get("id") or new_uid(),
                "title": (sc.get("title") or "Untitled sub-chapter").strip(),
            })
        norm_chapters.append({"id": ch_id, "title": ch_title, "subchapters": subs})

    outline_doc = {
        "project_id": project_id,
        "title": title,
        "chapters": norm_chapters,
        "citation_format": citation_format,
        "updated_at": utcnow_iso(),
    }
    await db.workspace_outlines.update_one(
        {"project_id": project_id},
        {"$set": outline_doc},
        upsert=True,
    )
    outline_doc["exists"] = True
    return outline_doc


def _find_subchapter(outline: dict, subchapter_id: str):
    """Return (chapter, subchapter) tuple for the given subchapter id; (None, None) if not found."""
    for ch in outline.get("chapters") or []:
        for sc in ch.get("subchapters") or []:
            if sc.get("id") == subchapter_id:
                return ch, sc
    return None, None


def _flatten_subchapter_order(outline: dict) -> List[dict]:
    """Return ordered list of subchapters as {chapter_id, chapter_title, id, title}."""
    out = []
    for ch in outline.get("chapters") or []:
        for sc in ch.get("subchapters") or []:
            out.append({
                "chapter_id": ch.get("id"),
                "chapter_title": ch.get("title"),
                "id": sc.get("id"),
                "title": sc.get("title"),
            })
    return out


@api.post("/projects/{project_id}/workspace/generate")
async def workspace_generate(project_id: str, payload: dict = Body(...)):
    await _project_or_404(project_id)
    outline = await db.workspace_outlines.find_one({"project_id": project_id}, {"_id": 0})
    if not outline:
        raise HTTPException(400, "Outline belum disusun. Buat Grand Outline terlebih dahulu.")

    subchapter_id = payload.get("subchapter_id")
    if not subchapter_id:
        raise HTTPException(400, "subchapter_id is required")
    chapter, subchapter = _find_subchapter(outline, subchapter_id)
    if not subchapter:
        raise HTTPException(404, "subchapter not found in outline")

    # Build project_documents pool
    docs = await db.documents.find(
        {"project_id": project_id, "status": "ready"}, {"_id": 0}
    ).to_list(500)
    if not docs:
        raise HTTPException(400, "Belum ada jurnal siap. Unggah PDF dan tunggu pemrosesan selesai.")

    project_documents = []
    for d in docs:
        sents = await db.sentences.find({"document_id": d["id"]}, {"_id": 0}).to_list(5000)
        project_documents.append({
            "id": d["id"],
            "title": d.get("title") or d.get("filename"),
            "authors": d.get("authors") or "",
            "year": d.get("year") or "",
            "sentences": sents,
        })

    settings = await _load_settings()
    model_id = payload.get("model") or settings.get("default_model") or default_model()
    if payload.get("persona"):
        settings = {**settings, "persona_id": payload["persona"]}
    provider, model_id = split_provider_model(model_id, settings)

    allow_sub = bool(payload.get("allow_subsubchapter", False))

    # Build existing citation map from prior workspace_contents badges across this project.
    # This guarantees a document keeps the same IEEE number across the whole draft.
    existing_map: dict = {}
    prior_contents = await db.workspace_contents.find(
        {"project_id": project_id}, {"_id": 0, "subchapter_id": 1, "badges": 1, "citation_map": 1}
    ).to_list(500)
    # Prefer a stored citation_map if any sub-chapter has one (highest numbers win merge).
    for pc in prior_contents:
        if pc.get("subchapter_id") == subchapter_id:
            continue  # we are regenerating this one — its badges will be replaced
        for did, num in (pc.get("citation_map") or {}).items():
            if isinstance(num, int) and (did not in existing_map or num < existing_map[did]):
                existing_map[did] = num
        # Also infer from badges' label like "[N]" when citation_map missing
        for b in pc.get("badges") or []:
            did = b.get("document_id")
            label = (b.get("label") or "").strip()
            m = _IEEE_LABEL_RE.match(label)
            if did and m:
                num = int(m.group(1))
                if did not in existing_map:
                    existing_map[did] = num

    # Sliding-window: if previous_paragraph not provided, try to compute it from
    # the most recent subchapter's stored content (flattened order, take subchapter
    # that appears just before this one).
    previous_paragraph = (payload.get("previous_paragraph") or "").strip()
    if not previous_paragraph:
        flat = _flatten_subchapter_order(outline)
        ids = [s["id"] for s in flat]
        try:
            idx = ids.index(subchapter_id)
        except ValueError:
            idx = 0
        for back in range(idx - 1, -1, -1):
            prev_sc_id = ids[back]
            prev_content = await db.workspace_contents.find_one(
                {"project_id": project_id, "subchapter_id": prev_sc_id}, {"_id": 0}
            )
            if prev_content and (prev_content.get("plain_paragraphs") or []):
                pars = prev_content.get("plain_paragraphs") or []
                if pars:
                    previous_paragraph = pars[-1]
                    break

    try:
        result = await generate_subchapter(
            project_id=project_id,
            paper_title=outline.get("title") or "Untitled paper",
            chapter_title=chapter.get("title") or "",
            subchapter_title=subchapter.get("title") or "",
            project_documents=project_documents,
            citation_format=outline.get("citation_format") or "ieee",
            previous_paragraph=previous_paragraph,
            allow_subsubchapter=allow_sub,
            existing_citation_map=existing_map,
            user_settings=settings,
            provider=provider,
            model=model_id,
        )
    except LLMJSONError as e:
        raise HTTPException(502, f"Model returned malformed JSON ({e})")

    # Persist generated content immediately so refresh keeps the draft
    saved = {
        "project_id": project_id,
        "subchapter_id": subchapter_id,
        "content": result["content_html"],
        "plain_paragraphs": result["plain_paragraphs"],
        "badges": result["badges"],
        "references_used": result["references_used"],
        "citation_format": outline.get("citation_format") or "ieee",
        "citation_map": result.get("citation_map") or {},
        "updated_at": utcnow_iso(),
    }
    await db.workspace_contents.update_one(
        {"project_id": project_id, "subchapter_id": subchapter_id},
        {"$set": saved},
        upsert=True,
    )
    return {
        "subchapter_id": subchapter_id,
        "content": result["content_html"],
        "badges": result["badges"],
        "references_used": result["references_used"],
    }


@api.get("/projects/{project_id}/workspace/content/{subchapter_id}")
async def workspace_get_content(project_id: str, subchapter_id: str):
    await _project_or_404(project_id)
    doc = await db.workspace_contents.find_one(
        {"project_id": project_id, "subchapter_id": subchapter_id}, {"_id": 0}
    )
    if not doc:
        return {
            "project_id": project_id,
            "subchapter_id": subchapter_id,
            "content": "",
            "badges": [],
            "references_used": [],
        }
    return doc


@api.put("/projects/{project_id}/workspace/content/{subchapter_id}")
async def workspace_save_content(project_id: str, subchapter_id: str, payload: dict = Body(...)):
    await _project_or_404(project_id)
    content = payload.get("content") or ""
    badges = payload.get("badges") or []
    plain_paragraphs = payload.get("plain_paragraphs") or []
    references_used = payload.get("references_used") or []
    update_doc = {
        "project_id": project_id,
        "subchapter_id": subchapter_id,
        "content": content,
        "badges": badges,
        "plain_paragraphs": plain_paragraphs,
        "references_used": references_used,
        "updated_at": utcnow_iso(),
    }
    await db.workspace_contents.update_one(
        {"project_id": project_id, "subchapter_id": subchapter_id},
        {"$set": update_doc},
        upsert=True,
    )
    return {"status": "saved", "updated_at": update_doc["updated_at"]}


@api.get("/projects/{project_id}/workspace/contents")
async def workspace_list_contents(project_id: str):
    """All sub-chapter contents for export and sliding-window utilities."""
    await _project_or_404(project_id)
    rows = await db.workspace_contents.find({"project_id": project_id}, {"_id": 0}).to_list(500)
    return {"items": rows}


@api.get("/documents/{document_id}/sentence/{sentence_id}")
async def get_sentence_detail(document_id: str, sentence_id: str):
    d = await _document_or_404(document_id)
    s = await db.sentences.find_one({"id": sentence_id, "document_id": document_id}, {"_id": 0})
    if not s:
        raise HTTPException(404, "sentence not found")
    return {
        "sentence_id": s["id"],
        "document_id": document_id,
        "text": s.get("text", ""),
        "page": s.get("page"),
        "section": s.get("section"),
        "x0": s.get("x0"),
        "y0": s.get("y0"),
        "x1": s.get("x1"),
        "y1": s.get("y1"),
        "page_width": s.get("page_width"),
        "page_height": s.get("page_height"),
        "document_title": d.get("title") or d.get("filename"),
        "document_authors": d.get("authors") or "",
        "document_year": d.get("year") or "",
    }


@api.post("/projects/{project_id}/workspace/insert-badge")
async def workspace_insert_badge(project_id: str, payload: dict = Body(...)):
    """Insert a citation badge (from Baca/Matrix/Tanya) into a target sub-chapter editor.

    Body:
        subchapter_id: str
        document_id: str
        sentence_id: str (optional — if omitted we still create a badge with quote/page)
        quote: str
        page: int|None
        label: str (optional override; otherwise computed from current outline format)
    """
    await _project_or_404(project_id)
    subchapter_id = payload.get("subchapter_id")
    document_id = payload.get("document_id")
    sentence_id = payload.get("sentence_id")
    quote = (payload.get("quote") or "").strip()
    page = payload.get("page")
    if not subchapter_id or not document_id:
        raise HTTPException(400, "subchapter_id and document_id are required")

    outline = await db.workspace_outlines.find_one({"project_id": project_id}, {"_id": 0})
    fmt = (outline or {}).get("citation_format") or "ieee"
    d = await db.documents.find_one({"id": document_id}, {"_id": 0})
    if not d:
        raise HTTPException(404, "document not found")

    label = payload.get("label")
    if not label:
        if fmt == "ieee":
            # Aggregate citation_map across ALL workspace_contents for this project
            # (not just the target sub-chapter) so the same paper keeps a consistent number.
            all_contents = await db.workspace_contents.find(
                {"project_id": project_id}, {"_id": 0, "subchapter_id": 1, "badges": 1, "citation_map": 1}
            ).to_list(500)
            global_map: dict = {}
            for pc in all_contents:
                for did, num in (pc.get("citation_map") or {}).items():
                    if isinstance(num, int) and (did not in global_map or num < global_map[did]):
                        global_map[did] = num
                for b in pc.get("badges") or []:
                    did2 = b.get("document_id")
                    m = _IEEE_LABEL_RE.match((b.get("label") or "").strip())
                    if did2 and m and did2 not in global_map:
                        global_map[did2] = int(m.group(1))
            if document_id in global_map:
                num = global_map[document_id]
            else:
                num = (max(global_map.values()) + 1) if global_map else 1
            label = f"[{num}]"
        elif fmt == "apa7":
            label = f"({d.get('authors') or 'Anon'}, {d.get('year') or 'n.d.'})"
        else:
            label = f"({d.get('authors') or 'Anon'}, {d.get('year') or 'n.d.'})"

    badge = {
        "badge_id": uuid.uuid4().hex[:10],
        "label": label,
        "document_id": document_id,
        "document_title": d.get("title") or d.get("filename"),
        "sentence_id": sentence_id or "",
        "page": page,
        "quote": quote,
        "authors": d.get("authors") or "",
        "year": d.get("year") or "",
    }
    return {"badge": badge, "citation_format": fmt}


@api.post("/projects/{project_id}/workspace/find-source")
async def workspace_find_source(project_id: str, payload: dict = Body(...)):
    """Find the best supporting sentence for a user-typed claim via BM25 across project docs."""
    await _project_or_404(project_id)
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "text is required")
    docs = await db.documents.find(
        {"project_id": project_id, "status": "ready"}, {"_id": 0}
    ).to_list(500)
    project_documents = []
    for d in docs:
        sents = await db.sentences.find({"document_id": d["id"]}, {"_id": 0}).to_list(5000)
        project_documents.append({
            "id": d["id"],
            "title": d.get("title") or d.get("filename"),
            "authors": d.get("authors") or "",
            "year": d.get("year") or "",
            "sentences": sents,
        })
    if not project_documents:
        return {"found": False, "reason": "no-documents"}
    hit = find_supporting_source(text, project_documents)
    if not hit:
        return {"found": False, "reason": "no-match"}
    return {"found": True, "source": hit}


@api.post("/settings/test-api-key")
async def settings_test_api_key(payload: dict = Body(...)):
    """Smoke-test a user-provided API key by issuing a single tiny generation."""
    provider = (payload.get("provider") or "").lower().strip()
    api_key = (payload.get("api_key") or "").strip()
    model = (payload.get("model") or "").strip()
    if provider not in ("gemini", "openai", "anthropic", "local"):
        raise HTTPException(400, "provider must be gemini, openai, anthropic, or local")
    if provider != "local" and not api_key:
        raise HTTPException(400, "api_key is required")

    default_models = {
        "gemini": "gemini-3-flash-preview",
        "openai": "gpt-5.4-mini",
        "anthropic": "claude-haiku-4-5",
    }

    # Build a one-off settings dict so resolve_key prefers the provided key
    fake_settings = {
        f"{provider}_key": api_key,
    }
    if provider == "local":
        endpoint = (payload.get("endpoint") or "").strip()
        if not endpoint:
            raise HTTPException(400, "endpoint is required for local provider")
        fake_settings["local_endpoint"] = endpoint
        fake_settings["local_api_key"] = api_key or "ollama"
        fake_settings["local_model"] = model or "llama3.1:8b"
        used_model = fake_settings["local_model"]
    else:
        used_model = model or default_models[provider]

    try:
        from app.services.llm import generate as llm_generate
        text = await llm_generate(
            f"keytest-{uuid.uuid4().hex[:6]}",
            "You are a connectivity probe. Reply with the single word OK.",
            "Respond with OK only.",
            provider=provider,
            model=used_model,
            user_settings=fake_settings,
            want_json=False,
        )
        sample = (text or "").strip().split("\n")[0][:80]
        return {
            "ok": True,
            "provider": provider,
            "model": used_model,
            "sample": sample or "(empty response)",
        }
    except Exception as e:  # noqa: BLE001
        return {
            "ok": False,
            "provider": provider,
            "model": used_model,
            "error": str(e)[:300],
        }


# ---- Mount ----
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown():
    client.close()
