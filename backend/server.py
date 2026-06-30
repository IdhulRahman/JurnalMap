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
    new_uid,
    utcnow_iso,
)
from app.services.document_processor import process_document
from app.services.evidence_service import find_evidence
from app.services.outlier_service import compute_outliers
from app.services.matrix_service import extract_row
from app.services.qa_service import answer_question


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

    background_tasks.add_task(process_document, db, doc_id, str(dest))
    return meta


@api.get("/documents/{document_id}", response_model=DocumentMeta)
async def get_document(document_id: str):
    d = await _document_or_404(document_id)
    return DocumentMeta(**d)


@api.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    d = await _document_or_404(document_id)
    await db.sentences.delete_many({"document_id": document_id})
    await db.claims.delete_many({"document_id": document_id})
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
        "claims": claims,
        "status": d.get("status"),
    }


# ---- Evidence ----
@api.post("/claims/{claim_id}/evidence", response_model=EvidenceResponse)
async def evidence_for_claim(claim_id: str):
    claim = await db.claims.find_one({"id": claim_id}, {"_id": 0})
    if not claim:
        raise HTTPException(404, "Claim not found")
    sentences = await db.sentences.find({"document_id": claim["document_id"]}, {"_id": 0}).sort("idx", 1).to_list(5000)
    items = await find_evidence(claim["text"], sentences, k=5)
    return EvidenceResponse(
        claim_id=claim_id,
        claim_text=claim["text"],
        items=[EvidenceItem(**i) for i in items],
    )


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
async def build_matrix(project_id: str, document_ids: Optional[List[str]] = Body(default=None, embed=True)):
    await _project_or_404(project_id)
    query = {"project_id": project_id, "status": "ready"}
    if document_ids:
        query["id"] = {"$in": document_ids}
    docs = await db.documents.find(query, {"_id": 0}).to_list(500)
    rows = []
    fields: List[str] = []
    for d in docs:
        sents = await db.sentences.find({"document_id": d["id"]}, {"_id": 0}).to_list(5000)
        row = await extract_row(d["id"], d.get("title") or d.get("filename"), sents)
        if not fields and row["cells"]:
            fields = [c["field"] for c in row["cells"]]
        rows.append(MatrixRow(document_id=row["document_id"], title=row["title"],
                              cells=[MatrixCell(**c) for c in row["cells"]]))
    if not fields:
        fields = ["objective", "method", "sample", "key_finding", "limitation"]
    return MatrixResponse(fields=fields, rows=rows)


# ---- Ask Library ----
@api.post("/projects/{project_id}/ask", response_model=AskResponse)
async def ask_library(project_id: str, payload: AskRequest):
    await _project_or_404(project_id)
    if not payload.question.strip():
        raise HTTPException(400, "question must not be empty")
    docs = await db.documents.find({"project_id": project_id, "status": "ready"}, {"_id": 0}).to_list(500)
    inputs = []
    for d in docs:
        sents = await db.sentences.find({"document_id": d["id"]}, {"_id": 0}).to_list(5000)
        inputs.append({"id": d["id"], "title": d.get("title") or d.get("filename"), "sentences": sents})
    res = await answer_question(payload.question, inputs)
    return AskResponse(
        question=res["question"],
        answer=res["answer"],
        citations=[Citation(**c) for c in res["citations"]],
        overall_tier=res["overall_tier"],
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
