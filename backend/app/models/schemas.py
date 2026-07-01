"""Pydantic schemas for JurnalMap."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Literal
import uuid

from pydantic import BaseModel, Field, ConfigDict


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_uid() -> str:
    return str(uuid.uuid4())


# ----- Project -----
class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class Project(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_uid)
    name: str
    description: str = ""
    created_at: str = Field(default_factory=utcnow_iso)
    document_count: int = 0
    owner_id: Optional[str] = None


# ----- Document -----
# queued = waiting in FIFO queue
# processing = currently being parsed by worker
# ready = parsed OK, sentences stored, summary optional (built on demand)
# failed = terminal failure — user can retry
DocStatus = Literal["queued", "processing", "ready", "failed"]


class DocumentMeta(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_uid)
    project_id: str
    filename: str
    status: DocStatus = "queued"
    error: Optional[str] = None
    page_count: int = 0
    title: Optional[str] = None
    summary: Optional[str] = None  # built on demand via /summarize
    sections: Optional[dict] = None  # {abstract, objective, method, results, conclusion}
    model_used: Optional[str] = None  # which LLM produced the current summary
    persona_used: Optional[str] = None
    summary_language: Optional[str] = None  # "id" or "en" — locked when first summary is built
    quality: Optional[dict] = None
    uploaded_at: str = Field(default_factory=utcnow_iso)
    queue_position: Optional[int] = None  # computed at read time, not persisted


# ----- Settings -----
PERSONAS = {
    "akademisi_ketat": {
        "label": "Akademisi Ketat",
        "prompt": "Anda adalah asisten akademik yang sangat presisi. Gunakan bahasa Indonesia formal. Jangan menambahkan interpretasi di luar teks sumber. Setiap klaim wajib merujuk ke kalimat spesifik di paper. Jika tidak ada bukti, katakan 'tidak ditemukan dalam teks'.",
    },
    "penjelasan_sederhana": {
        "label": "Penjelasan Sederhana",
        "prompt": "Anda adalah tutor yang menjelaskan riset kompleks dengan bahasa sederhana, analogi sehari-hari, dan contoh konkret. Akurasi tetap utama, tetapi gaya bahasa lebih santai dan mudah dipahami mahasiswa S1.",
    },
    "penulis_cepat": {
        "label": "Penulis Cepat",
        "prompt": "Anda adalah asisten penulisan efisien. Ringkasan padat maksimal 3 kalimat per bagian. Langsung ke poin utama tanpa basa-basi. Gaya semi-formal.",
    },
}


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = "singleton"
    theme: Literal["light", "dark"] = "light"
    persona_id: str = "akademisi_ketat"
    persona_custom: str = ""
    # API keys (optional override; if empty, falls back to EMERGENT_LLM_KEY)
    gemini_key: str = ""
    openai_key: str = ""
    anthropic_key: str = ""
    default_provider: str = "gemini"
    default_model: str = "gemini-3-flash-preview"


class AvailableModel(BaseModel):
    id: str  # e.g. "gemini-3-flash-preview"
    provider: str  # "gemini" / "openai" / "anthropic"
    label: str  # human-friendly


class Sentence(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_uid)
    document_id: str
    idx: int  # ordering across the document
    page: int  # 1-indexed
    page_width: float
    page_height: float
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    section: Optional[str] = None  # introduction / methods / results / discussion / other


class Claim(BaseModel):
    """A claim is one bullet inside the document summary."""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_uid)
    document_id: str
    idx: int
    text: str
    category: str = "finding"  # finding / method / objective / limitation


# ----- Evidence -----
class EvidenceItem(BaseModel):
    sentence_id: str
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    page_width: float
    page_height: float
    text: str
    tier: Literal["high", "medium", "low"]
    score: float
    rationale: str


class EvidenceResponse(BaseModel):
    claim_id: str
    claim_text: str
    items: List[EvidenceItem]


# ----- Outlier -----
class OutlierPoint(BaseModel):
    document_id: str
    title: str
    x: float
    y: float
    similarity_to_centroid: float
    is_outlier: bool
    keywords: List[str] = Field(default_factory=list)


class OutlierResponse(BaseModel):
    points: List[OutlierPoint]
    summary: str


# ----- Matrix -----
# ----- Matrix -----
MATRIX_METHODS = {
    "default": {
        "label": "Default (Tujuan/Metode/Sampel/Temuan/Keterbatasan)",
        "fields": ["objective", "method", "sample", "key_finding", "limitation"],
    },
    "gap_analysis": {
        "label": "Gap Analysis Matrix",
        "fields": ["what_is_known", "gap_identified", "why_unresolved", "opportunity"],
    },
    "method_comparison": {
        "label": "Method Comparison Matrix",
        "fields": ["study_design", "sampling", "data_collection", "analysis_technique", "validity"],
    },
    "feature_comparison": {
        "label": "Feature Comparison Matrix",
        "fields": ["features_supported", "dataset", "evaluation_metric", "performance"],
    },
    "experimental_comparison": {
        "label": "Experimental Comparison",
        "fields": ["hypothesis", "conditions", "controls", "results", "statistical_test"],
    },
}


class MatrixCell(BaseModel):
    field: str
    value: str
    excerpt: Optional[str] = None
    page: Optional[int] = None


class MatrixRow(BaseModel):
    document_id: str
    title: str
    cells: List[MatrixCell]


class MatrixResponse(BaseModel):
    fields: List[str]
    rows: List[MatrixRow]


# ----- Q&A -----
class AskRequest(BaseModel):
    question: str


class Citation(BaseModel):
    document_id: str
    document_title: str
    sentence_id: str
    page: int
    excerpt: str
    tier: Literal["high", "medium", "low"]


class AskResponse(BaseModel):
    question: str
    answer: str
    citations: List[Citation]
    overall_tier: Literal["high", "medium", "low"]
    model_used: Optional[str] = None
    persona_used: Optional[str] = None
    created_at: str = Field(default_factory=utcnow_iso)


class DocumentTitleUpdate(BaseModel):
    title: str
