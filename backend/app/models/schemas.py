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


# ----- Document -----
DocStatus = Literal["processing", "ready", "failed"]


class DocumentMeta(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_uid)
    project_id: str
    filename: str
    status: DocStatus = "processing"
    error: Optional[str] = None
    page_count: int = 0
    title: Optional[str] = None
    summary: Optional[str] = None  # short paragraph
    uploaded_at: str = Field(default_factory=utcnow_iso)


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
    created_at: str = Field(default_factory=utcnow_iso)
