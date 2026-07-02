"""PDF parsing using Docling — extract layout-aware elements and sentences with bounding boxes."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Dict, Any

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

SECTION_PATTERNS = {
    "abstract": re.compile(r"^\s*abstract\b", re.I),
    "introduction": re.compile(r"^\s*(1\.?\s+)?introduction\b", re.I),
    "methods": re.compile(r"^\s*(2\.?\s+)?(methods?|materials?\s+and\s+methods?|methodology)\b", re.I),
    "results": re.compile(r"^\s*(3\.?\s+)?results?\b", re.I),
    "discussion": re.compile(r"^\s*(4\.?\s+)?(discussion|discussions)\b", re.I),
    "conclusion": re.compile(r"^\s*(5\.?\s+)?conclusions?\b", re.I),
    "references": re.compile(r"^\s*references?\b", re.I),
}

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"\(])")


def split_sentences(text: str) -> List[str]:
    """Lightweight sentence splitter."""
    text = text.replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    if not text:
        return []
    parts = _SENTENCE_SPLIT.split(text)
    return [p.strip() for p in parts if len(p.strip()) > 5]


def parse_pdf(pdf_path: str | Path) -> Dict[str, Any]:
    """Return dict: { page_count, title, sentences, quality } using Docling."""
    pdf_path = str(pdf_path)
    
    # Configure Docling to disable OCR to avoid PyTorch errors and speed up processing
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )
    result = converter.convert(pdf_path)
    doc = result.document

    title = doc.name or ""
    sentences: List[Dict[str, Any]] = []
    current_section = "other"

    pages_with_text = set()
    tables_count = len(doc.tables) if hasattr(doc, "tables") else 0
    figures_count = len(doc.pictures) if hasattr(doc, "pictures") else 0

    # Iterate through all elements in the document using iterate_items()
    for item, level in doc.iterate_items():
        # Check text attribute
        if not hasattr(item, "text"):
            continue
        line_text = item.text.strip()
        if not line_text:
            continue

        # Extract page number and coordinate provenance
        page_idx = 1
        x0, y0, x1, y1 = 0, 0, 0, 0
        pw, ph = 612, 792  # Default to letter size in points

        if hasattr(item, "prov") and item.prov:
            prov = item.prov[0]
            page_idx = getattr(prov, "page_no", 1)
            pages_with_text.add(page_idx)
            
            bbox = getattr(prov, "bbox", None)
            if bbox:
                x0 = getattr(bbox, "l", 0)
                y0 = getattr(bbox, "t", 0)
                x1 = getattr(bbox, "r", 0)
                y1 = getattr(bbox, "b", 0)
                
            # Resolve page size from doc.pages
            if hasattr(doc, "pages") and doc.pages and page_idx in doc.pages:
                page_obj = doc.pages[page_idx]
                pw = getattr(page_obj, "width", 612)
                ph = getattr(page_obj, "height", 792)

        # Detect section headings
        label = str(getattr(item, "label", "")).lower()
        is_heading = "heading" in label or "title" in label
        if is_heading and len(line_text) < 60:
            for sec, pat in SECTION_PATTERNS.items():
                if pat.match(line_text):
                    current_section = sec
                    break

        for sent in split_sentences(line_text):
            sentences.append(
                {
                    "page": page_idx,
                    "page_width": pw,
                    "page_height": ph,
                    "x0": x0,
                    "y0": y0,
                    "x1": x1,
                    "y1": y1,
                    "text": sent,
                    "section": current_section,
                }
            )

    # Fallback title heuristics
    if not title and sentences:
        first_page = [s for s in sentences if s["page"] == 1]
        if first_page:
            title = first_page[0]["text"][:200]

    # Quality scoring based on pages containing successfully read text
    total_pages = len(doc.pages) if getattr(doc, "pages", None) else 1
    if not total_pages and pages_with_text:
        total_pages = max(pages_with_text)
    if not total_pages:
        total_pages = 1

    num_pages_with_text = len(pages_with_text)
    score = int(round((num_pages_with_text / total_pages) * 100)) if total_pages else 0
    label = "good" if score >= 80 else "fair" if score >= 50 else "poor"

    quality = {
        "score": score,
        "pages_with_text": num_pages_with_text,
        "total_pages": total_pages,
        "tables_count": tables_count,
        "figures_count": figures_count,
        "label": label,
    }

    return {
        "page_count": total_pages,
        "title": title,
        "sentences": sentences,
        "quality": quality,
    }
