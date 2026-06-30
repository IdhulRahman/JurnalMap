"""PDF parsing using PyMuPDF — extract sentences with bounding boxes."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Dict, Any

import fitz  # PyMuPDF


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
    """Lightweight sentence splitter (no spaCy needed)."""
    text = text.replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    if not text:
        return []
    parts = _SENTENCE_SPLIT.split(text)
    return [p.strip() for p in parts if len(p.strip()) > 5]


def parse_pdf(pdf_path: str | Path) -> Dict[str, Any]:
    """Return dict: { page_count, title, sentences, quality }.

    quality = {
        score: int (0-100),
        pages_with_text: int,
        total_pages: int,
        tables_count: int,
        figures_count: int,
        label: "good" | "fair" | "poor",
    }
    """
    pdf_path = str(pdf_path)
    doc = fitz.open(pdf_path)
    title = (doc.metadata or {}).get("title") or ""
    sentences: List[Dict[str, Any]] = []
    current_section = "other"

    pages_with_text = 0
    tables_count = 0
    figures_count = 0

    for page_idx, page in enumerate(doc):
        pw, ph = page.rect.width, page.rect.height
        blocks = page.get_text("dict").get("blocks", [])
        page_text_chars = 0
        page_has_table = False
        for block in blocks:
            btype = block.get("type", 0)
            if btype == 1:  # image block
                figures_count += 1
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                line_text = "".join(s.get("text", "") for s in spans).strip()
                if not line_text:
                    continue
                page_text_chars += len(line_text)
                # Section heading detection
                for sec, pat in SECTION_PATTERNS.items():
                    if pat.match(line_text) and len(line_text) < 60:
                        current_section = sec
                        break
                # Naive table heuristic: presence of "Table N" caption
                if re.match(r"^\s*table\s+\d+", line_text, re.I) and len(line_text) < 80:
                    page_has_table = True
                x0, y0, x1, y1 = line["bbox"]
                for sent in split_sentences(line_text):
                    sentences.append(
                        {
                            "page": page_idx + 1,
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
        if page_text_chars >= 50:  # heuristic threshold for "has readable text"
            pages_with_text += 1
        if page_has_table:
            tables_count += 1

    # heuristic title fallback
    if not title and sentences:
        first_page = [s for s in sentences if s["page"] == 1]
        if first_page:
            top = [s for s in first_page if s["y0"] < first_page[0]["page_height"] / 3]
            if top:
                title = max(top, key=lambda s: len(s["text"]))["text"][:200]

    page_count = doc.page_count
    doc.close()

    # Quality score = pages with text / total pages
    score = int(round((pages_with_text / page_count) * 100)) if page_count else 0
    if score >= 80:
        label = "good"
    elif score >= 50:
        label = "fair"
    else:
        label = "poor"

    quality = {
        "score": score,
        "pages_with_text": pages_with_text,
        "total_pages": page_count,
        "tables_count": tables_count,
        "figures_count": figures_count,
        "label": label,
    }
    return {
        "page_count": page_count,
        "title": title,
        "sentences": sentences,
        "quality": quality,
    }
