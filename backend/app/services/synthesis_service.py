"""Synthesis service — generates sub-chapter draft text grounded in project corpus.

Workflow:
1. Receive subchapter_id + outline context.
2. Build a multi-doc BM25 retrieval pool from all `ready` documents in the project.
3. Pull top-K fragments relevant to the sub-chapter (using sub-chapter title + chapter title + paper title).
4. Call LLM to compose 2-3 paragraphs (3-5 sentences each) using ONLY those fragments, with
   citation markers matching the chosen format (IEEE/APA7/Harvard).
5. Post-process to attach badge metadata (document, sentence, page) by parsing the
   bracketed markers the model emitted.
"""
from __future__ import annotations

import re
import uuid
from typing import List, Dict, Any, Optional

from .llm import persona_prefix, LLMJSONError, generate_json
from .retrieval import build_bm25, top_k


CITATION_FORMATS = {
    "ieee": {
        "label": "IEEE",
        "example": "[1]",
        "instruction": (
            "Use IEEE numeric markers like [1], [2]. Each marker number is provided to you in the "
            "DOCUMENT NUMBERING MAP. When you cite a fragment, look up its document_id in the map "
            "and use the corresponding number. ALSO add an inline tag in square brackets like [F3] "
            "to indicate which fragment supports the claim. The final output sentence looks like: "
            "'... claim text [1] [F3].'"
        ),
    },
    "apa7": {
        "label": "APA 7",
        "example": "(Smith, 2023)",
        "instruction": (
            "Use APA 7 style: (Author, Year). For multiple authors use (Smith & Jones, 2023) or "
            "(Smith et al., 2024). Place the marker at the END of the sentence. After each marker "
            "ALSO add an inline tag in square brackets like [F3] to indicate which fragment supports "
            "the claim. The final output sentence looks like: '... (Smith, 2023) [F3].'"
        ),
    },
    "harvard": {
        "label": "Harvard",
        "example": "(Smith, 2023)",
        "instruction": (
            "Use Harvard style: (Author, Year). For multiple authors use (Smith and Jones, 2023) or "
            "(Smith et al., 2024). Place the marker at the END of the sentence. After each marker "
            "ALSO add an inline tag in square brackets like [F3] to indicate which fragment supports "
            "the claim. The final output sentence looks like: '... (Smith and Jones, 2023) [F3].'"
        ),
    },
}


SYS_TEMPLATE = (
    "You are an academic synthesis assistant. Your job is to write 2-3 paragraphs for a "
    "specific sub-chapter of an academic paper. You MUST use ONLY the information found "
    "in the provided fragments. You may NOT introduce external knowledge.\n\n"
    "PARAGRAPH RULES:\n"
    "- Every paragraph MUST contain at least 3 and at most 5 sentences. No exceptions.\n"
    "- Do NOT cite trivial common facts. Cite only main claims, specific data, or key arguments.\n"
    "- One citation badge per sentence is enough. Max two badges per sentence ONLY if the sentence "
    "  fuses two claims from two different sources.\n\n"
    "FORMAT DECISION (apply per sub-chapter, decide from the planned CONTENT, not the title):\n"
    "- If the sub-chapter content is a list of equal, independent items (research questions, "
    "  objectives, hypotheses, steps, criteria, recommendations), use a LIST FORMAT (ordered "
    "  with <ol><li>…</li></ol> or bullets with <ul><li>…</li></ul>).\n"
    "- If the content is an explanation, argument, or flowing exposition, use NARRATIVE PARAGRAPHS "
    "  of 3-5 sentences each.\n"
    "- Do not decide format only from the sub-chapter title. Decide from what you are about to write. "
    "  When uncertain, prefer paragraphs.\n\n"
    "{subsub_rule}\n\n"
    "CITATION RULES:\n"
    "{citation_instruction}\n\n"
    "Output strictly as JSON of the shape:\n"
    "{{\n"
    '  "format": "paragraph" | "list",\n'
    '  "paragraphs": ["paragraph 1 text...", "paragraph 2 text..."],\n'
    '  "list_items": ["item 1 text...", "item 2 text..."],\n'
    '  "list_kind": "ordered" | "unordered"\n'
    "}}\n"
    "If format=='paragraph', leave list_items empty. If format=='list', leave paragraphs empty. "
    "Do not include markdown fences. Use plain text only.\n"
)


_SUBSUB_ALLOWED = (
    "SUB-SUB-HEADINGS: You MAY include internal sub-sub-headings (e.g. '2.1.1 Definisi Umum') "
    "within the content using <h3> tags if it makes the argument clearer. Sub-sub-headings are "
    "part of the content text, not separate structural entities."
)
_SUBSUB_FORBIDDEN = (
    "SUB-SUB-HEADINGS: You MUST NOT create sub-sub-headings (no '2.1.1', '2.1.2', '<h3>', etc.). "
    "Write only flat paragraphs or a single list."
)


def _fragment_id_re() -> re.Pattern:
    """Regex used to find fragment-id markers [F<number>] the model emits."""
    return re.compile(r"\[F(\d+)\]")


_IEEE_NUM_RE = re.compile(r"\[(\d+)\]")


def _build_pool(project_documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flatten {doc, sentences} into a pool with doc context attached to each sentence."""
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
    return pool


def _doc_label_apa(authors: str, year: str) -> str:
    a = (authors or "").strip() or "Anon"
    y = (year or "n.d.").strip()
    return f"({a}, {y})"


def _doc_label_harvard(authors: str, year: str) -> str:
    return _doc_label_apa(authors, year)


async def generate_subchapter(
    *,
    project_id: str,
    paper_title: str,
    chapter_title: str,
    subchapter_title: str,
    project_documents: List[Dict[str, Any]],
    citation_format: str = "ieee",
    previous_paragraph: str = "",
    top_k_fragments: int = 15,
    allow_subsubchapter: bool = False,
    existing_citation_map: Optional[Dict[str, int]] = None,
    user_settings: Optional[dict] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Compose a sub-chapter draft.

    existing_citation_map: pre-existing {document_id: ieee_number} mapping based on
    badges already present across the project. New documents are appended.
    """
    fmt = citation_format if citation_format in CITATION_FORMATS else "ieee"
    pool = _build_pool(project_documents)

    if not pool:
        return {
            "content_html": "<p><em>Tidak ada dokumen siap di proyek ini. Unggah jurnal terlebih dahulu.</em></p>",
            "plain_paragraphs": [],
            "badges": [],
            "references_used": [],
            "citation_map": dict(existing_citation_map or {}),
        }

    # BM25 retrieval — multi-doc pool flattened to sentences
    sentences_only = [p["sentence"] for p in pool]
    bm25 = build_bm25(sentences_only)
    query = " ".join(filter(None, [paper_title, chapter_title, subchapter_title]))
    ranked = top_k(bm25, sentences_only, query, k=top_k_fragments)
    if not ranked:
        ranked = [(p["sentence"], 0.0) for p in pool[:top_k_fragments]]

    # Build fragment list with stable F-ids
    fragments: List[Dict[str, Any]] = []
    for i, (sent, score) in enumerate(ranked, start=1):
        owner = next((p for p in pool if p["sentence"]["id"] == sent["id"]), None)
        if not owner:
            continue
        fragments.append({
            "frag_id": f"F{i}",
            "idx": i,
            "doc_id": owner["doc_id"],
            "doc_title": owner["doc_title"],
            "authors": owner["authors"],
            "year": owner["year"],
            "sentence": sent,
            "score": score,
        })

    # Pre-build the IEEE document numbering map.
    # Start from existing_citation_map (numbers already used by previous sub-chapters)
    citation_map: Dict[str, int] = dict(existing_citation_map or {})
    next_num = (max(citation_map.values()) + 1) if citation_map else 1
    # Pre-assign provisional numbers for fragments' docs so LLM can see them all.
    for f in fragments:
        did = f["doc_id"]
        if did not in citation_map:
            citation_map[did] = next_num
            next_num += 1

    # Build mapping table for the LLM (used only for IEEE)
    if fmt == "ieee":
        unique = []
        seen = set()
        for f in fragments:
            if f["doc_id"] in seen:
                continue
            seen.add(f["doc_id"])
            unique.append((f["doc_id"], f["doc_title"], citation_map[f["doc_id"]]))
        map_text = "\nDOCUMENT NUMBERING MAP (use exactly these numbers in citation brackets):\n"
        for did, title, num in unique:
            map_text += f"  [{num}] = {title[:60]} (doc_id={did[:8]}…)\n"
    else:
        map_text = ""

    fragments_text = "\n".join(
        f"{f['frag_id']}. [Doc: {f['doc_title'][:60]}, p.{f['sentence'].get('page','?')}, doc_id={f['doc_id'][:8]}…] \"{f['sentence']['text']}\""
        for f in fragments
    )

    cf = CITATION_FORMATS[fmt]
    subsub_rule = _SUBSUB_ALLOWED if allow_subsubchapter else _SUBSUB_FORBIDDEN
    sys_msg = persona_prefix(user_settings) + SYS_TEMPLATE.format(
        citation_instruction=cf["instruction"],
        subsub_rule=subsub_rule,
    )

    user_msg = (
        f"Paper title: {paper_title}\n"
        f"Chapter: {chapter_title}\n"
        f"Sub-chapter to write: {subchapter_title}\n\n"
        f"Citation format: {cf['label']} (example marker: {cf['example']})\n"
        f"{map_text}\n"
        f"Available fragments:\n{fragments_text}\n\n"
    )
    if previous_paragraph:
        user_msg += (
            "Previous paragraph (continue from this with a natural transition; do not repeat it):\n"
            f"\"{previous_paragraph}\"\n\n"
        )
    user_msg += (
        "Decide format first (paragraph or list). If paragraph, write 2-3 paragraphs of 3-5 "
        "sentences each. If list, write 3-7 items. Use ONLY the fragments above. Cite only "
        "main claims; include [F<n>] for every citation so we can resolve sources."
    )

    try:
        data = await generate_json(
            f"workspace-{uuid.uuid4().hex[:8]}",
            sys_msg,
            user_msg,
            provider=provider,
            model=model,
            user_settings=user_settings,
        )
    except LLMJSONError:
        return {
            "content_html": "<p><em>Model gagal menghasilkan JSON yang valid. Coba model lain atau ulangi.</em></p>",
            "plain_paragraphs": [],
            "badges": [],
            "references_used": [],
            "citation_map": citation_map,
        }

    if not isinstance(data, dict):
        data = {}
    fmt_out = (data.get("format") or "paragraph").strip().lower()
    if fmt_out not in ("paragraph", "list"):
        fmt_out = "paragraph"
    paragraphs = data.get("paragraphs") or []
    if not isinstance(paragraphs, list):
        paragraphs = []
    paragraphs = [str(p).strip() for p in paragraphs if str(p).strip()]
    list_items = data.get("list_items") or []
    if not isinstance(list_items, list):
        list_items = []
    list_items = [str(it).strip() for it in list_items if str(it).strip()]
    list_kind = (data.get("list_kind") or "unordered").lower()
    if list_kind not in ("ordered", "unordered"):
        list_kind = "unordered"

    # Parse fragment-id markers and replace with badge spans
    frag_pat = _fragment_id_re()
    frag_by_id = {f["frag_id"]: f for f in fragments}

    badges: List[Dict[str, Any]] = []
    used_doc_ids: set = set()
    final_citation_map: Dict[str, int] = dict(existing_citation_map or {})
    final_next = (max(final_citation_map.values()) + 1) if final_citation_map else 1

    def _make_badge(frag_key: str) -> Optional[str]:
        nonlocal final_next
        frag = frag_by_id.get(frag_key)
        if not frag:
            return None
        doc_id = frag["doc_id"]
        if fmt == "ieee":
            if doc_id not in final_citation_map:
                final_citation_map[doc_id] = final_next
                final_next += 1
            label = f"[{final_citation_map[doc_id]}]"
        elif fmt == "apa7":
            label = _doc_label_apa(frag["authors"], frag["year"])
        else:
            label = _doc_label_harvard(frag["authors"], frag["year"])
        badge_id = uuid.uuid4().hex[:10]
        badges.append({
            "badge_id": badge_id,
            "label": label,
            "document_id": doc_id,
            "document_title": frag["doc_title"],
            "sentence_id": frag["sentence"]["id"],
            "page": frag["sentence"].get("page"),
            "quote": frag["sentence"]["text"],
            "authors": frag["authors"],
            "year": frag["year"],
        })
        used_doc_ids.add(doc_id)
        return (
            f'<span class="jm-citation-badge" data-badge-id="{badge_id}" '
            f'data-document-id="{doc_id}" data-sentence-id="{frag["sentence"]["id"]}" '
            f'data-page="{frag["sentence"].get("page","")}" '
            f'contenteditable="false">{label}</span>'
        )

    def _process(text: str) -> str:
        def _sub(m: re.Match) -> str:
            badge_html = _make_badge(f"F{m.group(1)}")
            return badge_html if badge_html else m.group(0)
        out = frag_pat.sub(_sub, text)
        # For IEEE we also need to strip any [N] the model already emitted (since we render
        # via badge from [F<n>]). Keep them only if no badge follows immediately.
        if fmt == "ieee":
            # Remove naked numeric markers that aren't followed by a badge for the SAME number
            # to avoid duplication like "[3] [3]". Pragmatic: drop all naked [N] tokens since
            # the badge already contains the visible number.
            out = _IEEE_NUM_RE.sub("", out)
            out = re.sub(r"\s{2,}", " ", out)
        return out

    html_parts: List[str] = []
    if fmt_out == "list" and list_items:
        tag = "ol" if list_kind == "ordered" else "ul"
        items_html = "".join(f"<li>{_process(it)}</li>" for it in list_items)
        html_parts.append(f"<{tag}>{items_html}</{tag}>")
    else:
        for para in paragraphs:
            html_parts.append(f"<p>{_process(para)}</p>")

    # Build references_used in the order they appear in citation_map (low→high)
    sorted_docs = sorted(final_citation_map.items(), key=lambda kv: kv[1])
    refs_used: List[Dict[str, Any]] = []
    for doc_id, _num in sorted_docs:
        if doc_id not in used_doc_ids:
            continue
        # find any fragment for metadata
        frag = next((f for f in fragments if f["doc_id"] == doc_id), None)
        if not frag:
            continue
        refs_used.append({
            "document_id": doc_id,
            "title": frag["doc_title"],
            "authors": frag["authors"],
            "year": frag["year"],
        })

    return {
        "content_html": "\n".join(html_parts) if html_parts else "<p></p>",
        "plain_paragraphs": paragraphs if fmt_out == "paragraph" else list_items,
        "badges": badges,
        "references_used": refs_used,
        "citation_map": final_citation_map,
    }


# ---------------------------------------------------------------------------
# Manual claim verification (Revision 8 — "Cari Sumber" button)
# ---------------------------------------------------------------------------

def find_supporting_source(
    claim_text: str,
    project_documents: List[Dict[str, Any]],
    *,
    min_score_ratio: float = 0.18,
) -> Optional[Dict[str, Any]]:
    """Return the best supporting sentence from the project corpus for `claim_text`.

    Uses BM25 over all project sentences and returns top-1 if the relative score is high
    enough. min_score_ratio is a heuristic on the share of query tokens that hit.
    """
    if not claim_text or not claim_text.strip():
        return None
    pool = _build_pool(project_documents)
    if not pool:
        return None
    sentences_only = [p["sentence"] for p in pool]
    bm25 = build_bm25(sentences_only)
    ranked = top_k(bm25, sentences_only, claim_text, k=3)
    if not ranked:
        return None
    best_sent, best_score = ranked[0]
    # Normalize: score / number of query tokens. BM25Okapi typical scores can be quite
    # variable; we just check there is some lexical overlap. The frontend can decide
    # whether to surface this or not.
    from .retrieval import tokenize
    qtoks = tokenize(claim_text)
    if not qtoks or best_score <= 0:
        return None
    ratio = best_score / max(len(qtoks), 1)
    if ratio < min_score_ratio:
        return None
    owner = next((p for p in pool if p["sentence"]["id"] == best_sent["id"]), None)
    if not owner:
        return None
    return {
        "document_id": owner["doc_id"],
        "sentence_id": best_sent["id"],
        "quote": best_sent["text"],
        "page": best_sent.get("page"),
        "document_title": owner["doc_title"],
        "document_authors": owner["authors"],
        "document_year": owner["year"],
        "score": best_score,
        "score_ratio": ratio,
    }
