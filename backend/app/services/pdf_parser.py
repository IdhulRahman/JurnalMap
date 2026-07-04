"""PDF parsing using PyMuPDF & pymupdf4llm — extract sentences with bounding boxes."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Dict, Any

from .hybrid_pdf_parser import HybridParser


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


def align_words_to_sentences(sents: List[str], words: List[Any]) -> List[List[Any]]:
    """Align list of words to list of sentences, returning a list of word-lists (one per sentence)."""
    # Normalize words
    word_tokens = []
    for w in words:
        norm = re.sub(r"[^a-zA-Z0-9]", "", w.text).lower()
        if norm:
            word_tokens.append((norm, w))
            
    # Normalize sentences into token sequences
    sent_token_seqs = []
    for s in sents:
        tokens = [re.sub(r"[^a-zA-Z0-9]", "", t).lower() for t in s.split()]
        tokens = [t for t in tokens if t]
        sent_token_seqs.append(tokens)
        
    results = [[] for _ in sents]
    word_idx = 0
    n_words = len(word_tokens)
    
    for s_idx, tokens in enumerate(sent_token_seqs):
        if not tokens:
            continue
        for token in tokens:
            found = False
            # Search window of 10 words ahead
            for offset in range(10):
                curr_idx = word_idx + offset
                if curr_idx >= n_words:
                    break
                if word_tokens[curr_idx][0] == token:
                    # Match found! Add all words from word_idx to curr_idx to this sentence
                    for i in range(word_idx, curr_idx + 1):
                        results[s_idx].append(word_tokens[i][1])
                    word_idx = curr_idx + 1
                    found = True
                    break
            if not found:
                pass
                
    return results


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
    
    parser = HybridParser()
    doc = parser.parse(pdf_path)
    
    sentences: List[Dict[str, Any]] = []
    current_section = "other"
    
    pages_with_text = 0
    tables_count = 0
    figures_count = 0
    
    for page in doc.pages:
        pw, ph = page.width, page.height
        page_has_text = False
        page_has_table = False
        
        for block in page.blocks:
            # Type classification
            if block.type == "image":
                figures_count += 1
                continue
            elif block.type == "table":
                tables_count += 1
                page_has_table = True
                
                # Extract markdown table as a single sentence block
                x0, y0, x1, y1 = block.bbox
                sentences.append(
                    {
                        "page": page.page_number,
                        "page_width": pw,
                        "page_height": ph,
                        "x0": x0,
                        "y0": y0,
                        "x1": x1,
                        "y1": y1,
                        "text": f"[TABLE]\n{block.markdown.strip()}",
                        "section": current_section,
                    }
                )
                continue
            
            block_text = block.markdown.strip()
            if not block_text:
                continue
                
            page_has_text = True
            
            # If it's a heading block, detect section heading updates
            if block.type == "heading":
                clean_text = block_text.strip().lower()
                for sec, pat in SECTION_PATTERNS.items():
                    if pat.match(clean_text) and len(clean_text) < 60:
                        current_section = sec
                        break
            
            # Split block text into sentences (handles sentences spanning multiple lines correctly)
            sents = split_sentences(block_text)
            
            # Align words to sentences to get accurate bounding boxes
            aligned_sentence_words = align_words_to_sentences(sents, block.words)
            
            for s_idx, sent in enumerate(sents):
                matching_words = aligned_sentence_words[s_idx]
                if matching_words:
                    x0 = min(w.bbox[0] for w in matching_words)
                    y0 = min(w.bbox[1] for w in matching_words)
                    x1 = max(w.bbox[2] for w in matching_words)
                    y1 = max(w.bbox[3] for w in matching_words)
                else:
                    x0, y0, x1, y1 = block.bbox
                
                sentences.append(
                    {
                        "page": page.page_number,
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
                
        if page_has_text or page_has_table:
            pages_with_text += 1
            
    # Fallback title logic
    title = doc.metadata.source_file
    if sentences:
        first_page = [s for s in sentences if s["page"] == 1]
        if first_page:
            top = [s for s in first_page if s["y0"] < first_page[0]["page_height"] / 3]
            if top:
                title = max(top, key=lambda s: len(s["text"]))["text"][:200]
                
    page_count = doc.metadata.total_pages
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
