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
