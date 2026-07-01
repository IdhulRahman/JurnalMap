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
    Depends,
    status,
)
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
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
from app.models.user import (
    User,
    UserCreate,
    UserLogin,
    TokenResponse,
    ForgotPasswordRequest,
    ChangePasswordRequest,
)
from app.services.document_processor import process_document, process_document_parse_only, regenerate_summary
from app.services.evidence_service import find_evidence
from app.services.outlier_service import compute_outliers
from app.services.network_service import compute_network
from app.services.matrix_service import extract_row, fields_for
from app.services.qa_service import answer_question
from app.services.verification_service import check_text
from app.services.llm import split_provider_model, emergent_key, default_model, LLMJSONError
from app.services.auth_service import hash_password, verify_password, create_access_token, decode_token
from app.services import cache as app_cache
from app.services import queue as queue_worker


UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", str(ROOT_DIR / "uploads")))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Max files per upload request
MAX_FILES_PER_UPLOAD = int(os.environ.get("MAX_FILES_PER_UPLOAD", "5"))
# Max file size in MB
MAX_UPLOAD_SIZE_MB = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "50"))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="JurnalMap API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("jurnalmap")

# ── JWT Security ─────────────────────────────────────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> dict:
    """Dependency: extract and validate JWT, return user dict."""
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


# ── Helpers ──────────────────────────────────────────────────────────────────

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


async def _document_or_forbidden(document_id: str, current_user: dict) -> dict:
    """Fetch a document and verify caller owns its parent project."""
    d = await _document_or_404(document_id)
    project = await db.projects.find_one({"id": d["project_id"]}, {"_id": 0, "owner_id": 1})
    if project and not current_user.get("is_admin"):
        owner = project.get("owner_id")
        if owner and owner != current_user["id"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your document")
    return d


# ── Health ────────────────────────────────────────────────────────────────────

@api.get("/")
async def root():
    return {"app": "JurnalMap", "status": "ok"}


# ── Auth ──────────────────────────────────────────────────────────────────────

# Lockout policy: 3 consecutive failed attempts → 30-second cooldown.
MAX_LOGIN_ATTEMPTS = int(os.environ.get("MAX_LOGIN_ATTEMPTS", "3"))
LOCKOUT_SECONDS = int(os.environ.get("LOCKOUT_SECONDS", "30"))


def _now_ts() -> float:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).timestamp()


def _lockout_active(user_doc: dict) -> tuple[bool, int]:
    """Return (is_locked, remaining_seconds)."""
    locked_until = user_doc.get("locked_until") or 0
    if not locked_until:
        return False, 0
    now = _now_ts()
    if now < locked_until:
        return True, int(locked_until - now) + 1
    return False, 0


@api.post("/auth/register", response_model=TokenResponse)
async def register(payload: UserCreate):
    """Register a new user account.

    Password policy is enforced by `UserCreate` validator: length>=8, upper, digit, symbol.
    """
    username = payload.username.strip().lower()
    if not username or len(username) < 3:
        raise HTTPException(400, "Username must be at least 3 characters")

    existing = await db.users.find_one({"username": username})
    if existing:
        raise HTTPException(409, "Username already taken")

    # Prevent duplicate emails (case-insensitive)
    email_norm = payload.email.strip().lower()
    existing_email = await db.users.find_one({"email": email_norm})
    if existing_email:
        raise HTTPException(409, "Email already registered")

    user_id = new_uid()
    hashed = hash_password(payload.password)
    user_doc = {
        "id": user_id,
        "username": username,
        "email": email_norm,
        "is_admin": False,
        "password_hash": hashed,
        "created_at": utcnow_iso(),
        "failed_attempts": 0,
        "locked_until": 0,
    }
    await db.users.insert_one(user_doc)

    token = create_access_token(user_id, username)
    user = User(**{k: v for k, v in user_doc.items() if k != "password_hash"})
    return TokenResponse(access_token=token, user=user)


@api.post("/auth/login", response_model=TokenResponse)
async def login(payload: UserLogin):
    """Login with username and password, returns JWT token.

    After 3 consecutive failures the account is locked for 30 seconds.
    """
    username = payload.username.strip().lower()
    user_doc = await db.users.find_one({"username": username})
    if not user_doc:
        # Do not leak whether the username exists.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    # Enforce lockout
    is_locked, remaining = _lockout_active(user_doc)
    if is_locked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": "Account temporarily locked. Please wait or use forgot-password.",
                "locked": True,
                "remaining_seconds": remaining,
                "max_attempts": MAX_LOGIN_ATTEMPTS,
            },
        )

    if not verify_password(payload.password, user_doc.get("password_hash", "")):
        attempts = int(user_doc.get("failed_attempts", 0)) + 1
        update: dict = {"failed_attempts": attempts}
        if attempts >= MAX_LOGIN_ATTEMPTS:
            update["locked_until"] = _now_ts() + LOCKOUT_SECONDS
            update["failed_attempts"] = 0  # reset after lockout kicks in
        await db.users.update_one({"id": user_doc["id"]}, {"$set": update})

        remaining_attempts = max(MAX_LOGIN_ATTEMPTS - attempts, 0)
        detail = {
            "message": "Invalid username or password",
            "remaining_attempts": remaining_attempts,
            "max_attempts": MAX_LOGIN_ATTEMPTS,
        }
        if attempts >= MAX_LOGIN_ATTEMPTS:
            detail["locked"] = True
            detail["remaining_seconds"] = LOCKOUT_SECONDS
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)

    # Success: reset counters
    await db.users.update_one({"id": user_doc["id"]}, {"$set": {"failed_attempts": 0, "locked_until": 0}})

    token = create_access_token(user_doc["id"], username)
    user = User(**{k: v for k, v in user_doc.items() if k != "password_hash"})
    return TokenResponse(access_token=token, user=user)


@api.post("/auth/forgot-password", response_model=TokenResponse)
async def forgot_password(payload: ForgotPasswordRequest):
    """Reset password when the user proves ownership via matching username + email.

    NOTE: In production this should send an email with a signed token. For MVP
    we accept an in-band reset when username and email both match a record.
    """
    username = payload.username.strip().lower()
    email = payload.email.strip().lower()
    user_doc = await db.users.find_one({"username": username})
    if not user_doc:
        raise HTTPException(404, "Account not found")
    if (user_doc.get("email") or "").lower() != email:
        raise HTTPException(400, "Username and email do not match our records")

    hashed = hash_password(payload.new_password)
    await db.users.update_one(
        {"id": user_doc["id"]},
        {"$set": {
            "password_hash": hashed,
            "failed_attempts": 0,
            "locked_until": 0,
        }},
    )
    token = create_access_token(user_doc["id"], username)
    user = User(**{k: v for k, v in user_doc.items() if k not in ("password_hash",)})
    return TokenResponse(access_token=token, user=user)


@api.post("/auth/change-password")
async def change_password(payload: ChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    """Authenticated password change. Requires current password."""
    full = await db.users.find_one({"id": current_user["id"]})
    if not full or not verify_password(payload.current_password, full.get("password_hash", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")
    if payload.current_password == payload.new_password:
        raise HTTPException(400, "New password must differ from current password")
    hashed = hash_password(payload.new_password)
    await db.users.update_one(
        {"id": current_user["id"]},
        {"$set": {"password_hash": hashed, "failed_attempts": 0, "locked_until": 0}},
    )
    return {"changed": True}


@api.get("/auth/me", response_model=User)
async def me(current_user: dict = Depends(get_current_user)):
    """Return the currently authenticated user."""
    return User(**current_user)


# ── Projects ──────────────────────────────────────────────────────────────────

@api.post("/projects", response_model=Project)
async def create_project(payload: ProjectCreate, current_user: dict = Depends(get_current_user)):
    p = Project(name=payload.name.strip() or "Untitled project", description=payload.description.strip())
    doc = p.model_dump()
    doc["owner_id"] = current_user["id"]
    await db.projects.insert_one(doc)
    return p


def _owner_filter(current_user: dict) -> dict:
    """Return a Mongo filter that scopes reads to owned + legacy (no owner_id) projects.

    Admin users see everything.
    """
    if current_user.get("is_admin"):
        return {}
    # Include legacy documents without owner_id so admin's own historical projects
    # remain accessible (they will be silently claimed by whoever accesses them).
    return {"$or": [{"owner_id": current_user["id"]}, {"owner_id": {"$exists": False}}]}


@api.get("/projects", response_model=List[Project])
async def list_projects(current_user: dict = Depends(get_current_user)):
    rows = await db.projects.find(_owner_filter(current_user), {"_id": 0}).sort("created_at", -1).to_list(500)
    for r in rows:
        r["document_count"] = await db.documents.count_documents({"project_id": r["id"]})
    return [Project(**r) for r in rows]


async def _project_or_forbidden(project_id: str, current_user: dict) -> dict:
    """Fetch a project and ensure the caller owns it (or is admin)."""
    p = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Project not found")
    if not current_user.get("is_admin"):
        owner = p.get("owner_id")
        if owner and owner != current_user["id"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your project")
    return p


@api.get("/projects/{project_id}", response_model=Project)
async def get_project(project_id: str, current_user: dict = Depends(get_current_user)):
    p = await _project_or_forbidden(project_id, current_user)
    p["document_count"] = await db.documents.count_documents({"project_id": project_id})
    return Project(**p)


@api.delete("/projects/{project_id}")
async def delete_project(project_id: str, current_user: dict = Depends(get_current_user)):
    await _project_or_forbidden(project_id, current_user)
    docs = await db.documents.find({"project_id": project_id}, {"_id": 0, "id": 1}).to_list(1000)
    doc_ids = [d["id"] for d in docs]
    if doc_ids:
        await db.sentences.delete_many({"document_id": {"$in": doc_ids}})
        await db.claims.delete_many({"document_id": {"$in": doc_ids}})
        await db.matrix_cache.delete_many({"document_id": {"$in": doc_ids}})
        for did in doc_ids:
            fp = UPLOAD_DIR / f"{did}.pdf"
            if fp.exists():
                try:
                    fp.unlink()
                except OSError:
                    pass
            app_cache.invalidate_bm25(did)
    app_cache.invalidate_outlier(project_id)
    await db.documents.delete_many({"project_id": project_id})
    await db.workspace_outlines.delete_many({"project_id": project_id})
    await db.workspace_contents.delete_many({"project_id": project_id})
    await db.check_runs.delete_many({"project_id": project_id})
    await db.projects.delete_one({"id": project_id})
    return {"deleted": True}


# ── Documents ─────────────────────────────────────────────────────────────────

@api.get("/projects/{project_id}/documents", response_model=List[DocumentMeta])
async def list_documents(project_id: str, current_user: dict = Depends(get_current_user)):
    await _project_or_forbidden(project_id, current_user)
    rows = await db.documents.find({"project_id": project_id}, {"_id": 0}).sort("uploaded_at", -1).to_list(500)
    # Attach transient queue_position for queued/processing docs
    for r in rows:
        pos = await queue_worker.compute_queue_position(db, r)
        if pos is not None:
            r["queue_position"] = pos
    return [DocumentMeta(**r) for r in rows]


@api.post("/projects/{project_id}/documents", response_model=List[DocumentMeta])
async def upload_documents(
    project_id: str,
    files: List[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Upload up to N PDF files. All are enqueued for background parsing.

    Files are inserted with status='queued' and picked up FIFO by the single
    queue worker (concurrency=1). No LLM call happens at upload time.
    """
    await _project_or_forbidden(project_id, current_user)

    if len(files) > MAX_FILES_PER_UPLOAD:
        raise HTTPException(400, f"Maximum {MAX_FILES_PER_UPLOAD} files per upload")

    results: List[DocumentMeta] = []

    for file in files:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(400, f"Only PDF files are accepted (got: {file.filename!r})")

        doc_id = new_uid()
        dest = UPLOAD_DIR / f"{doc_id}.pdf"

        # Write file with size guard
        written = 0
        async with aiofiles.open(dest, "wb") as out:
            while True:
                chunk = await file.read(1 << 20)  # 1 MB chunks
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_UPLOAD_SIZE_BYTES:
                    await out.close()
                    dest.unlink(missing_ok=True)
                    raise HTTPException(413, f"File '{file.filename}' exceeds {MAX_UPLOAD_SIZE_MB} MB limit")
                await out.write(chunk)

        meta = DocumentMeta(id=doc_id, project_id=project_id, filename=file.filename, status="queued")
        await db.documents.insert_one(meta.model_dump())
        results.append(meta)

    # Invalidate outlier cache for this project since new docs are coming
    app_cache.invalidate_outlier(project_id)
    return results


@api.post("/documents/{document_id}/retry", response_model=DocumentMeta)
async def retry_document(document_id: str, current_user: dict = Depends(get_current_user)):
    """Re-queue a failed (or stuck) document. Clears error and returns it to 'queued'."""
    d = await _document_or_forbidden(document_id, current_user)
    fp = UPLOAD_DIR / f"{document_id}.pdf"
    if not fp.exists():
        raise HTTPException(400, "Original file is missing, cannot retry. Please re-upload.")
    if d.get("status") == "processing":
        raise HTTPException(400, "Document is already processing")
    # Reset for a fresh run
    from app.models.schemas import utcnow_iso
    await db.documents.update_one(
        {"id": document_id},
        {"$set": {
            "status": "queued",
            "error": None,
            "uploaded_at": utcnow_iso(),
        }},
    )
    updated = await db.documents.find_one({"id": document_id}, {"_id": 0})
    return DocumentMeta(**updated)


@api.get("/projects/{project_id}/queue")
async def get_project_queue(project_id: str, current_user: dict = Depends(get_current_user)):
    """Return queue status for a project's documents."""
    await _project_or_forbidden(project_id, current_user)
    docs = await db.documents.find(
        {"project_id": project_id},
        {"_id": 0, "id": 1, "filename": 1, "status": 1, "uploaded_at": 1, "error": 1},
    ).sort("uploaded_at", 1).to_list(500)
    items = []
    for d in docs:
        pos = await queue_worker.compute_queue_position(db, d)
        items.append({
            "id": d["id"],
            "filename": d.get("filename"),
            "status": d.get("status"),
            "queue_position": pos,
            "error": d.get("error"),
        })
    global_summary = await queue_worker.queue_summary(db)
    return {"items": items, **global_summary}


@api.get("/documents/{document_id}", response_model=DocumentMeta)
async def get_document(document_id: str, current_user: dict = Depends(get_current_user)):
    d = await _document_or_forbidden(document_id, current_user)
    return DocumentMeta(**d)


@api.patch("/documents/{document_id}", response_model=DocumentMeta)
async def update_document(document_id: str, payload: DocumentTitleUpdate, current_user: dict = Depends(get_current_user)):
    """Update editable document fields. Currently: title only."""
    d = await _document_or_forbidden(document_id, current_user)
    new_title = (payload.title or "").strip()
    if not new_title:
        raise HTTPException(400, "title must not be empty")
    if len(new_title) > 500:
        new_title = new_title[:500]
    await db.documents.update_one({"id": document_id}, {"$set": {"title": new_title}})
    await db.matrix_cache.update_many({"document_id": document_id}, {"$set": {"title": new_title}})
    d["title"] = new_title
    return DocumentMeta(**d)


@api.delete("/documents/{document_id}")
async def delete_document(document_id: str, current_user: dict = Depends(get_current_user)):
    d = await _document_or_forbidden(document_id, current_user)
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
    app_cache.invalidate_bm25(document_id)
    return {"deleted": True, "id": d["id"]}


@api.get("/documents/{document_id}/pdf")
async def serve_pdf(document_id: str, current_user: dict = Depends(get_current_user)):
    await _document_or_forbidden(document_id, current_user)
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
    """Return the list of models the user can pick. Admin-configured only.

    - Cloud model exposed if EMERGENT_LLM_KEY is set (default: LLM_MODEL env var)
    - Local LLM exposed if LOCAL_LLM_ENABLED is truthy in server env
    """
    models: list[dict] = []
    if emergent_key():
        primary_id = os.environ.get("LLM_MODEL", "gemini-2.0-flash")
        # Detect provider from model id for the label prefix.
        prov, _ = split_provider_model(primary_id, None)
        models.append({"id": primary_id, "provider": prov, "label": f"{primary_id} (administrator)"})
        # Also expose a couple of common alternates from the emergent stack.
        alternates = [
            ("gemini-3-flash-preview", "gemini"),
            ("gpt-5.4-mini", "openai"),
            ("claude-haiku-4-5", "anthropic"),
        ]
        seen = {primary_id}
        for mid, prov in alternates:
            if mid in seen:
                continue
            seen.add(mid)
            models.append({"id": mid, "provider": prov, "label": f"{mid} (administrator)"})

    # Admin-provided local LLM (Ollama / vLLM / gemma etc.)
    if os.environ.get("LOCAL_LLM_ENABLED", "false").lower() in ("1", "true", "yes"):
        local_name = os.environ.get("LOCAL_LLM_NAME", "gemma-llm")
        models.append({
            "id": local_name,
            "provider": "local",
            "label": f"{local_name} (administrator)",
        })
    return models


def _mask(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return value[:4] + "***" + value[-4:]


# ── Settings ──────────────────────────────────────────────────────────────────

@api.get("/settings")
async def get_settings(_: dict = Depends(get_current_user)):
    s = await _load_settings()
    return {
        "theme": s.get("theme", "light"),
        "persona_id": s.get("persona_id", "akademisi_ketat"),
        "persona_custom": s.get("persona_custom", ""),
        "output_language": s.get("output_language", "en"),
        "ui_language": s.get("ui_language", "id"),
        "default_model": s.get("default_model") or default_model(),
        "gemini_key_masked": _mask(s.get("gemini_key")),
        "openai_key_masked": _mask(s.get("openai_key")),
        "anthropic_key_masked": _mask(s.get("anthropic_key")),
        "has_gemini_key": bool(s.get("gemini_key")),
        "has_openai_key": bool(s.get("openai_key")),
        "has_anthropic_key": bool(s.get("anthropic_key")),
        "local_endpoint": s.get("local_endpoint", ""),
        "local_api_key_masked": _mask(s.get("local_api_key")) if s.get("local_api_key") and s.get("local_api_key") != "ollama" else "",
        "local_model": s.get("local_model", ""),
        "has_local": bool(s.get("local_endpoint") and s.get("local_model")),
        "personas": [{"id": k, "label": v["label"]} for k, v in PERSONAS.items()] + [{"id": "custom", "label": "Custom"}],
        "matrix_methods": [{"id": k, "label": v["label"]} for k, v in MATRIX_METHODS.items()],
        "available_models": _models_for(s),
    }


@api.put("/settings")
async def update_settings(payload: dict = Body(...), _: dict = Depends(get_current_user)):
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
    return await get_settings(_)


# ── Summary ───────────────────────────────────────────────────────────────────

@api.get("/documents/{document_id}/summary")
async def get_summary(document_id: str, current_user: dict = Depends(get_current_user)):
    d = await _document_or_forbidden(document_id, current_user)
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
async def get_status(document_id: str, current_user: dict = Depends(get_current_user)):
    """Status endpoint that returns processing state + structured summary when ready."""
    d = await _document_or_forbidden(document_id, current_user)
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


def _apply_language(settings: dict, language: Optional[str]) -> dict:
    """Return a shallow-copied settings dict with output_language overridden."""
    if not language:
        return settings
    lang = language.strip().lower()
    if lang not in ("id", "en"):
        return settings
    out = dict(settings or {})
    out["output_language"] = lang
    return out


def _local_llm_env_settings() -> dict:
    """Convert admin-configured local LLM env vars into settings dict overrides."""
    enabled = os.environ.get("LOCAL_LLM_ENABLED", "false").lower() in ("1", "true", "yes")
    if not enabled:
        return {}
    return {
        "local_endpoint": os.environ.get("LOCAL_LLM_ENDPOINT", ""),
        "local_model": os.environ.get("LOCAL_LLM_NAME", "gemma-llm"),
        "local_api_key": os.environ.get("LOCAL_LLM_API_KEY", "ollama"),
    }


@api.post("/documents/{document_id}/summarize")
async def resummarize(
    document_id: str,
    model: Optional[str] = None,
    language: Optional[str] = None,
    payload: dict = Body(default={}),
    current_user: dict = Depends(get_current_user),
):
    """Generate (or regenerate) the summary for a document.

    Query params:
      - model:    optional model id override (must be one of `available_models`)
      - language: "id" or "en" — output language for this summary
    """
    d = await _document_or_forbidden(document_id, current_user)
    if d.get("status") != "ready":
        raise HTTPException(409, "Document is not ready yet (still queued/processing/failed)")
    settings = await _load_settings()
    # Merge admin local-LLM env into settings so provider routing can pick it up
    settings = {**settings, **_local_llm_env_settings()}
    settings = _apply_language(settings, language)
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
    # Persist chosen language on the document so Matriks etc. can reuse it
    await db.documents.update_one(
        {"id": document_id},
        {"$set": {"summary_language": (settings.get("output_language") or "en")}},
    )
    return await get_summary(document_id, current_user)


# ── Evidence ──────────────────────────────────────────────────────────────────

@api.post("/claims/{claim_id}/evidence", response_model=EvidenceResponse)
async def evidence_for_claim(claim_id: str, current_user: dict = Depends(get_current_user)):
    claim = await db.claims.find_one({"id": claim_id}, {"_id": 0})
    if not claim:
        raise HTTPException(404, "Claim not found")
    # Enforce ownership through the claim's document
    await _document_or_forbidden(claim["document_id"], current_user)
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
async def evidence_for_section(document_id: str, payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Find evidence in a doc for arbitrary text."""
    await _document_or_forbidden(document_id, current_user)
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


# ── Outliers ──────────────────────────────────────────────────────────────────

@api.get("/projects/{project_id}/outliers", response_model=OutlierResponse)
async def project_outliers(project_id: str, current_user: dict = Depends(get_current_user)):
    await _project_or_forbidden(project_id, current_user)

    # Check cache first
    cached = app_cache.get_outlier(project_id)
    if cached:
        return OutlierResponse(**cached)

    docs = await db.documents.find({"project_id": project_id, "status": "ready"}, {"_id": 0}).to_list(500)
    payload = []
    for d in docs:
        sents = await db.sentences.find({"document_id": d["id"]}, {"_id": 0}).to_list(5000)
        payload.append({"id": d["id"], "title": d.get("title") or d.get("filename"), "sentences": sents})
    res = compute_outliers(payload)

    # Cache the result
    app_cache.set_outlier(project_id, res)
    return OutlierResponse(**res)


# ── Matrix ────────────────────────────────────────────────────────────────────

@api.post("/projects/{project_id}/matrix", response_model=MatrixResponse)
async def build_matrix(
    project_id: str,
    document_ids: Optional[List[str]] = Body(default=None, embed=True),
    refresh: bool = Body(default=False, embed=True),
    method: str = Body(default="default", embed=True),
    current_user: dict = Depends(get_current_user),
):
    await _project_or_forbidden(project_id, current_user)
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


# ── Ask Library ───────────────────────────────────────────────────────────────

@api.post("/projects/{project_id}/ask", response_model=AskResponse)
async def ask_library(
    project_id: str,
    payload: AskRequest,
    model: Optional[str] = None,
    language: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    await _project_or_forbidden(project_id, current_user)
    if not payload.question.strip():
        raise HTTPException(400, "question must not be empty")
    docs = await db.documents.find({"project_id": project_id, "status": "ready"}, {"_id": 0}).to_list(500)
    inputs = []
    for d in docs:
        sents = await db.sentences.find({"document_id": d["id"]}, {"_id": 0}).to_list(5000)
        inputs.append({"id": d["id"], "title": d.get("title") or d.get("filename"), "sentences": sents})
    settings = await _load_settings()
    settings = {**settings, **_local_llm_env_settings()}
    settings = _apply_language(settings, language)
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


# ── Network Graph ─────────────────────────────────────────────────────────────

@api.get("/projects/{project_id}/network")
async def project_network(project_id: str, current_user: dict = Depends(get_current_user)):
    """Composite-similarity network graph for the project's ready documents.

    Composite = 0.5 * semantic + 0.3 * keyword_jaccard + 0.2 * topic_match.
    Semantic uses sentence-transformers when available, TF cosine fallback otherwise.
    """
    await _project_or_forbidden(project_id, current_user)
    docs = await db.documents.find(
        {"project_id": project_id, "status": "ready"}, {"_id": 0},
    ).to_list(500)
    payload = []
    for d in docs:
        sents = await db.sentences.find({"document_id": d["id"]}, {"_id": 0}).to_list(5000)
        payload.append({"id": d["id"], "title": d.get("title") or d.get("filename"), "sentences": sents})
    res = compute_network(payload)
    return res


# ── Config (public models the admin exposes) ─────────────────────────────────

@api.get("/config")
async def app_config():
    """Public server config: available models, embedding backend, upload limits."""
    settings = await _load_settings()
    return {
        "available_models": _models_for(settings),
        "default_model": os.environ.get("LLM_MODEL", "gemini-2.0-flash"),
        "embedding_model": os.environ.get("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"),
        "embedding_enabled": os.environ.get("EMBEDDING_ENABLED", "true").lower() in ("1", "true", "yes"),
        "local_llm_enabled": os.environ.get("LOCAL_LLM_ENABLED", "false").lower() in ("1", "true", "yes"),
        "max_files_per_upload": MAX_FILES_PER_UPLOAD,
        "max_upload_size_mb": MAX_UPLOAD_SIZE_MB,
    }


# ── Check & Fix ───────────────────────────────────────────────────────────────

@api.get("/documents/{document_id}/sentence/{sentence_id}")
async def get_sentence_detail(document_id: str, sentence_id: str, current_user: dict = Depends(get_current_user)):
    d = await _document_or_forbidden(document_id, current_user)
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


@api.post("/projects/{project_id}/check")
async def check_fix(project_id: str, payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
    await _project_or_forbidden(project_id, current_user)
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "text is required")
    bibliography = (payload.get("bibliography") or "").strip()
    document_ids = payload.get("document_ids") or None
    citation_format = (payload.get("citation_format") or "ieee").lower()

    query = {"project_id": project_id, "status": "ready"}
    if document_ids:
        query["id"] = {"$in": document_ids}
    docs = await db.documents.find(query, {"_id": 0}).to_list(500)
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

    result = check_text(
        text=text,
        bibliography=bibliography,
        project_documents=project_documents,
        citation_format=citation_format,
    )

    await db.check_runs.update_one(
        {"project_id": project_id},
        {"$set": {
            "project_id": project_id,
            "text": text,
            "bibliography": bibliography,
            "document_ids": document_ids,
            "citation_format": citation_format,
            "units": result["units"],
            "summary": result["summary"],
            "annotated_html": result["annotated_html"],
            "badges": result["badges"],
            "references_used": result["references_used"],
            "updated_at": utcnow_iso(),
        }},
        upsert=True,
    )
    return {
        "units": result["units"],
        "summary": result["summary"],
        "annotated_html": result["annotated_html"],
        "badges": result["badges"],
        "references_used": result["references_used"],
    }


@api.get("/projects/{project_id}/check")
async def get_last_check(project_id: str, current_user: dict = Depends(get_current_user)):
    await _project_or_forbidden(project_id, current_user)
    doc = await db.check_runs.find_one({"project_id": project_id}, {"_id": 0})
    if not doc:
        return {"exists": False}
    doc["exists"] = True
    return doc


@api.post("/settings/test-api-key")
async def settings_test_api_key(payload: dict = Body(...), _: dict = Depends(get_current_user)):
    """Smoke-test a user-provided API key."""
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

    fake_settings = {f"{provider}_key": api_key}
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


# ── Cache stats (debug endpoint) ─────────────────────────────────────────────

@api.get("/cache/stats")
async def cache_stats(_: dict = Depends(get_current_user)):
    """Return in-memory cache statistics for debugging."""
    return app_cache.cache_stats()


# ── Mount & Middleware ────────────────────────────────────────────────────────

app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Startup: Seed default admin ───────────────────────────────────────────────

@app.on_event("startup")
async def seed_admin():
    """Create default admin account if it doesn't exist."""
    admin_username = os.environ.get("ADMIN_USERNAME", "admin").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin")

    existing = await db.users.find_one({"username": admin_username})
    if not existing:
        user_id = new_uid()
        hashed = hash_password(admin_password)
        await db.users.insert_one({
            "id": user_id,
            "username": admin_username,
            "email": os.environ.get("ADMIN_EMAIL", "admin@jurnalmap.local"),
            "is_admin": True,
            "password_hash": hashed,
            "created_at": utcnow_iso(),
            "failed_attempts": 0,
            "locked_until": 0,
        })
        logger.info("Default admin account '%s' created.", admin_username)
    else:
        logger.info("Admin account '%s' already exists.", admin_username)

    # Ensure MongoDB indexes for performance
    await db.users.create_index("username", unique=True)
    await db.users.create_index("email")
    await db.projects.create_index("created_at")
    await db.projects.create_index("owner_id")
    await db.documents.create_index([("project_id", 1), ("uploaded_at", -1)])
    await db.documents.create_index([("project_id", 1), ("status", 1)])
    await db.documents.create_index([("status", 1), ("uploaded_at", 1)])
    await db.sentences.create_index([("document_id", 1), ("idx", 1)])
    await db.claims.create_index([("document_id", 1), ("idx", 1)])

    # Reset any "processing" docs that were interrupted by a restart
    reset = await db.documents.update_many(
        {"status": "processing"},
        {"$set": {"status": "queued"}},
    )
    if reset.modified_count:
        logger.info("Reset %d in-flight documents to 'queued' on startup", reset.modified_count)

    # Start the single-worker PDF processing queue
    queue_worker.start_worker(db, UPLOAD_DIR)


@app.on_event("shutdown")
async def shutdown():
    await queue_worker.stop_worker()
    client.close()
