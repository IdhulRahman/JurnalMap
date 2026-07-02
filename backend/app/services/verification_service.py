"""Verification service — "Check & Fix" feature.

Given user-pasted text from another AI (ChatGPT/Claude/Gemini/...), split it into
meaningful units (paragraphs/list items), score each unit against the project's
documents via BM25, classify as:
    - "supported" (green) — strong evidence in the corpus
    - "similar"   (yellow) — partial match, paraphrase, or weak overlap
    - "unsupported" (red) — no meaningful match

Returns annotated HTML, badges, references-used, and a summary report.
"""
from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .retrieval import build_bm25, rrf_top_k, tokenize


# Tunable thresholds. Score is computed as bm25_score / max(query_tokens,1).
# These cutoffs were chosen empirically: BM25Okapi typical "good" matches sit
# around 1.5-3.5 per token, partial matches 0.4-1.5, noise < 0.4.
SUPPORT_THRESHOLD = 1.0
SIMILAR_THRESHOLD = 0.35


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\u00C0-\u017F\"\'\(])")


def _split_sentences(text: str) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    parts = _SENT_SPLIT.split(text)
    return [p.strip() for p in parts if p.strip()]


def split_into_units(text: str) -> List[Dict[str, Any]]:
    """Slice a free-form text into verification units.

    Rules (Revision B):
      1. Split by paragraphs (double newline).
      2. If a paragraph has >5 sentences, chunk it into sub-units of MIN 2 sentences
         (keep local context).
      3. Short paragraphs (1-2 sentences) stay whole.
      4. For markdown-ish lists ("- " or "* " or "N. "), each item = one unit.

    Returns:
        [{kind: "paragraph"|"list_item", text: str, list_kind: "ordered"|"unordered"|None}]
    """
    if not text or not text.strip():
        return []
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = re.split(r"\n\s*\n", text)
    units: List[Dict[str, Any]] = []

    list_line_re = re.compile(r"^\s*(?:[-*\u2022]|\d+[.)])\s+(.+)$")

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        # Check if the paragraph is a list (every non-empty line matches list pattern)
        lines = [ln for ln in para.split("\n") if ln.strip()]
        if len(lines) >= 2 and all(list_line_re.match(ln) for ln in lines):
            ordered = bool(re.match(r"^\s*\d+[.)]\s+", lines[0]))
            for ln in lines:
                m = list_line_re.match(ln)
                if m:
                    units.append({
                        "kind": "list_item",
                        "text": m.group(1).strip(),
                        "list_kind": "ordered" if ordered else "unordered",
                    })
            continue

        # Normal paragraph
        sentences = _split_sentences(para)
        if not sentences:
            continue
        if len(sentences) <= 5:
            units.append({"kind": "paragraph", "text": " ".join(sentences), "list_kind": None})
        else:
            # Chunk into pairs (min 2 sentences per unit). If trailing single, append to last.
            i = 0
            while i < len(sentences):
                # Default 2 sentences. Use 3 if more than 6 remaining to balance.
                step = 3 if (len(sentences) - i) >= 6 else 2
                end = min(i + step, len(sentences))
                chunk = sentences[i:end]
                if len(chunk) < 2 and units and units[-1]["kind"] == "paragraph":
                    units[-1]["text"] += " " + chunk[0]
                else:
                    units.append({"kind": "paragraph", "text": " ".join(chunk), "list_kind": None})
                i = end
    return units


def _bibliography_boost(unit_text: str, bibliography: str) -> float:
    """Heuristic: how many tokens of `unit_text` also appear in `bibliography`.

    Returns a number in [0, 1] used as a multiplicative boost (1+x) on the BM25 score.
    """
    if not bibliography or not bibliography.strip():
        return 0.0
    u = set(tokenize(unit_text))
    b = set(tokenize(bibliography))
    if not u or not b:
        return 0.0
    return len(u & b) / max(len(u), 1)


def _ieee_number_for(doc_id: str, mapping: Dict[str, int], next_num_ref: list) -> int:
    if doc_id not in mapping:
        mapping[doc_id] = next_num_ref[0]
        next_num_ref[0] += 1
    return mapping[doc_id]


def _escape(s: str) -> str:
    return (
        str(s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def check_text(
    *,
    text: str,
    bibliography: str = "",
    project_documents: List[Dict[str, Any]],
    citation_format: str = "ieee",
) -> Dict[str, Any]:
    """Verify each unit of `text` against the project corpus.

    Returns:
        {
            "units": [
                {
                    unit_id, kind, text, status (supported|similar|unsupported),
                    score, badge (when supported|similar), suggestions (for unsupported)
                }
            ],
            "summary": {total, supported, similar, unsupported, references_used},
            "annotated_html": "<div class='cf-units'>...</div>",
            "badges": [...]  # all created badges
        }
    """
    units = split_into_units(text)
    if not units:
        return {
            "units": [],
            "summary": {"total": 0, "supported": 0, "similar": 0, "unsupported": 0},
            "annotated_html": "<div class='cf-units'><p><em>Tidak ada teks untuk diperiksa.</em></p></div>",
            "badges": [],
            "references_used": [],
        }

    # Build a pool of (sentence, doc-meta) for fast BM25
    pool: List[Dict[str, Any]] = []
    for d in project_documents:
        for s in d.get("sentences") or []:
            pool.append({
                "doc_id": d["id"],
                "doc_title": d.get("title") or "Untitled",
                "authors": d.get("authors") or "",
                "year": d.get("year") or "",
                "sentence": s,
            })

    if not pool:
        # No corpus → everything unsupported
        annotated, summary, badges, refs = _empty_corpus_render(units)
        return {
            "units": annotated,
            "summary": summary,
            "annotated_html": _render_html(annotated, badges_by_unit={}),
            "badges": badges,
            "references_used": refs,
        }

    sentences_only = [p["sentence"] for p in pool]
    bm25 = build_bm25(sentences_only)

    # Maintain global IEEE numbering across units (Revision C from previous round, kept)
    ieee_map: Dict[str, int] = {}
    next_num = [1]
    references_index: Dict[str, Dict[str, Any]] = {}

    badges: List[Dict[str, Any]] = []
    badges_by_unit: Dict[str, List[Dict[str, Any]]] = {}
    annotated_units: List[Dict[str, Any]] = []

    for u in units:
        unit_id = uuid.uuid4().hex[:10]
        qtext = u["text"]
        qtoks = tokenize(qtext)
        if not qtoks:
            annotated_units.append({
                "unit_id": unit_id,
                "kind": u["kind"],
                "list_kind": u.get("list_kind"),
                "text": qtext,
                "status": "unsupported",
                "score": 0.0,
                "suggestions": [],
            })
            continue

        ranked = rrf_top_k(bm25, sentences_only, qtext, k=3)
        if not ranked:
            annotated_units.append({
                "unit_id": unit_id,
                "kind": u["kind"],
                "list_kind": u.get("list_kind"),
                "text": qtext,
                "status": "unsupported",
                "score": 0.0,
                "suggestions": [],
            })
            continue

        best_sent, best_score = ranked[0]
        
        # Determine classification using semantic cosine similarity if available
        cosine_val = best_sent.get("cosine_score", 0.0)
        
        if cosine_val > 0.0:
            if cosine_val >= 0.80:
                status = "supported"
            elif cosine_val >= 0.50:
                status = "similar"
            else:
                status = "unsupported"
            effective = cosine_val
        else:
            # Fallback to legacy token-overlap (BM25) scoring if embeddings are offline/missing
            score_per_token = best_score / max(len(qtoks), 1)
            boost = _bibliography_boost(qtext, bibliography)
            effective = score_per_token * (1.0 + boost)
            if effective >= SUPPORT_THRESHOLD:
                status = "supported"
            elif effective >= SIMILAR_THRESHOLD:
                status = "similar"
            else:
                status = "unsupported"

        unit_entry: Dict[str, Any] = {
            "unit_id": unit_id,
            "kind": u["kind"],
            "list_kind": u.get("list_kind"),
            "text": qtext,
            "status": status,
            "score": round(effective, 3),
            "suggestions": [],
        }

        if status in ("supported", "similar"):
            owner = next((p for p in pool if p["sentence"]["id"] == best_sent["id"]), None)
            if owner:
                doc_id = owner["doc_id"]
                num = _ieee_number_for(doc_id, ieee_map, next_num)
                if citation_format == "apa7":
                    label = f"({owner['authors'] or 'Anon'}, {owner['year'] or 'n.d.'})"
                elif citation_format == "harvard":
                    label = f"({owner['authors'] or 'Anon'}, {owner['year'] or 'n.d.'})"
                else:
                    label = f"[{num}]"

                badge = {
                    "badge_id": uuid.uuid4().hex[:10],
                    "label": label,
                    "document_id": doc_id,
                    "document_title": owner["doc_title"],
                    "sentence_id": best_sent["id"],
                    "page": best_sent.get("page"),
                    "quote": best_sent["text"],
                    "authors": owner["authors"],
                    "year": owner["year"],
                    "status": status,
                }
                unit_entry["badge"] = badge
                badges.append(badge)
                badges_by_unit[unit_id] = [badge]
                if doc_id not in references_index:
                    references_index[doc_id] = {
                        "document_id": doc_id,
                        "title": owner["doc_title"],
                        "authors": owner["authors"],
                        "year": owner["year"],
                    }

        if status == "unsupported":
            # Provide suggestions from top-3 if any have similarity score in similar-range
            suggestions: List[Dict[str, Any]] = []
            for sent, score in ranked[:3]:
                s_score = (score / max(len(qtoks), 1))
                if s_score >= 0.15:  # very loose, only to offer "did you mean?"
                    owner = next((p for p in pool if p["sentence"]["id"] == sent["id"]), None)
                    if owner:
                        suggestions.append({
                            "document_id": owner["doc_id"],
                            "document_title": owner["doc_title"],
                            "sentence_id": sent["id"],
                            "quote": sent["text"],
                            "page": sent.get("page"),
                            "authors": owner["authors"],
                            "year": owner["year"],
                            "score": round(s_score, 3),
                        })
            unit_entry["suggestions"] = suggestions

        annotated_units.append(unit_entry)

    summary = {
        "total": len(annotated_units),
        "supported": sum(1 for u in annotated_units if u["status"] == "supported"),
        "similar": sum(1 for u in annotated_units if u["status"] == "similar"),
        "unsupported": sum(1 for u in annotated_units if u["status"] == "unsupported"),
    }
    refs_used = list(references_index.values())
    annotated_html = _render_html(annotated_units, badges_by_unit)

    return {
        "units": annotated_units,
        "summary": summary,
        "annotated_html": annotated_html,
        "badges": badges,
        "references_used": refs_used,
    }


def _empty_corpus_render(units: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int], List[Dict[str, Any]], List[Dict[str, Any]]]:
    annotated = [
        {
            "unit_id": uuid.uuid4().hex[:10],
            "kind": u["kind"],
            "list_kind": u.get("list_kind"),
            "text": u["text"],
            "status": "unsupported",
            "score": 0.0,
            "suggestions": [],
        }
        for u in units
    ]
    summary = {
        "total": len(annotated),
        "supported": 0,
        "similar": 0,
        "unsupported": len(annotated),
    }
    return annotated, summary, [], []


def _render_html(units: List[Dict[str, Any]], badges_by_unit: Dict[str, List[Dict[str, Any]]]) -> str:
    parts: List[str] = ['<div class="cf-units">']
    # Group consecutive list_item units sharing same list_kind into a single <ol>/<ul>
    i = 0
    while i < len(units):
        u = units[i]
        if u["kind"] == "list_item":
            list_kind = u.get("list_kind") or "unordered"
            tag = "ol" if list_kind == "ordered" else "ul"
            parts.append(f"<{tag} class=\"cf-list\">")
            while i < len(units) and units[i]["kind"] == "list_item" and (units[i].get("list_kind") or "unordered") == list_kind:
                parts.append(_render_unit(units[i], badges_by_unit, container="li"))
                i += 1
            parts.append(f"</{tag}>")
        else:
            parts.append(_render_unit(u, badges_by_unit, container="p"))
            i += 1
    parts.append("</div>")
    return "\n".join(parts)


def _render_unit(unit: Dict[str, Any], badges_by_unit: Dict[str, List[Dict[str, Any]]], container: str) -> str:
    status = unit["status"]
    text_html = _escape(unit["text"])
    badges = badges_by_unit.get(unit["unit_id"]) or []
    badge_html_chunks: List[str] = []
    for b in badges:
        badge_html_chunks.append(
            f'<span class="jm-citation-badge" data-badge-id="{_escape(b["badge_id"])}" '
            f'data-document-id="{_escape(b["document_id"])}" '
            f'data-sentence-id="{_escape(b.get("sentence_id") or "")}" '
            f'data-page="{_escape(str(b.get("page") or ""))}" '
            f'contenteditable="false">{_escape(b["label"])}</span>'
        )
    badge_html = " " + " ".join(badge_html_chunks) if badge_html_chunks else ""
    return (
        f'<{container} class="cf-unit cf-{status}" '
        f'data-unit-id="{_escape(unit["unit_id"])}" '
        f'data-status="{status}">'
        f'{text_html}{badge_html}'
        f'</{container}>'
    )
