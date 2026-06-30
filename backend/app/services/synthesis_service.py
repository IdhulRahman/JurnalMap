"""Synthesis service — generates sub-chapter draft text grounded in project corpus.

Workflow:
1. Receive subchapter_id + outline context.
2. Build a multi-doc BM25 retrieval pool from all `ready` documents in the project.
3. Pull top-K fragments relevant to the sub-chapter (using sub-chapter title + chapter title + paper title).
4. Call LLM to compose 2-3 paragraphs using ONLY those fragments, with citation markers
   matching the chosen format (IEEE/APA7/Harvard).
5. Post-process to attach badge metadata (document, sentence, page) by parsing the
   bracketed markers the model emitted.
"""
from __future__ import annotations

import re
import uuid
from typing import List, Dict, Any, Optional

from .llm import generate, persona_prefix, LLMJSONError, generate_json
from .retrieval import build_bm25, top_k


CITATION_FORMATS = {
    "ieee": {
        "label": "IEEE",
        "example": "[1]",
        "instruction": (
            "Use IEEE numeric markers like [1], [2]. Each marker corresponds to a specific "
            "fragment ID from the provided list. Use the exact fragment ID number as the marker "
            "(e.g., fragment F3 must be cited as [3]). Place the marker at the END of the sentence."
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
    "Every factual claim MUST be supported by an inline citation. {citation_instruction}\n\n"
    "You MAY include internal sub-sub-headings (e.g. '2.1.1 Definisi Umum') within the content "
    "if it makes the argument clearer. Such sub-sub-headings are part of the content text, "
    "not separate structural entities.\n\n"
    "Output strictly as JSON of the shape:\n"
    "{{\n"
    '  "paragraphs": ["paragraph 1 text...", "paragraph 2 text..."],\n'
    '  "citations": [\n'
    '    {{"fragment_id": "F1", "marker": "[1]"}},\n'
    '    ...\n'
    "  ]\n"
    "}}\n"
    "Do not include markdown fences. Use plain text only. Do not invent fragments.\n"
)


def _fragment_id_re_for_format(fmt: str) -> re.Pattern:
    """Regex used to find fragment-id markers the model emits."""
    if fmt == "ieee":
        return re.compile(r"\[(\d+)\]")
    # APA / Harvard: model emits [F<number>] after the author-year marker
    return re.compile(r"\[F(\d+)\]")


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


def _doc_label_ieee(idx: int) -> str:
    return f"[{idx}]"


def _doc_label_apa(authors: str, year: str) -> str:
    a = (authors or "").strip()
    y = (year or "n.d.").strip()
    if not a:
        a = "Anon"
    return f"({a}, {y})"


def _doc_label_harvard(authors: str, year: str) -> str:
    a = (authors or "").strip()
    y = (year or "n.d.").strip()
    if not a:
        a = "Anon"
    return f"({a}, {y})"


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
    user_settings: Optional[dict] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Compose a sub-chapter draft.

    Returns:
        {
            "content_html": "<p>...</p>",   # HTML with inline <span class='jm-badge' ...> badges
            "plain_paragraphs": [..],
            "badges": [
                {badge_id, label, document_id, document_title, sentence_id, page, quote}
            ],
            "references_used": [
                {document_id, title, authors, year}
            ]
        }
    """
    fmt = citation_format if citation_format in CITATION_FORMATS else "ieee"
    pool = _build_pool(project_documents)

    if not pool:
        return {
            "content_html": "<p><em>Tidak ada dokumen siap di proyek ini. Unggah jurnal terlebih dahulu.</em></p>",
            "plain_paragraphs": [],
            "badges": [],
            "references_used": [],
        }

    # BM25 retrieval — multi-doc pool flattened to sentences
    sentences_only = [p["sentence"] for p in pool]
    bm25 = build_bm25(sentences_only)
    query = " ".join(filter(None, [paper_title, chapter_title, subchapter_title]))
    ranked = top_k(bm25, sentences_only, query, k=top_k_fragments)
    if not ranked:
        # Soft fallback — pick first N
        ranked = [(p["sentence"], 0.0) for p in pool[:top_k_fragments]]

    # Build fragment list with stable F-ids
    fragments: List[Dict[str, Any]] = []
    for i, (sent, score) in enumerate(ranked, start=1):
        # find owner from pool
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

    fragments_text = "\n".join(
        f"{f['frag_id']}. [Doc: {f['doc_title'][:60]}, p.{f['sentence'].get('page','?')}] \"{f['sentence']['text']}\""
        for f in fragments
    )

    cf = CITATION_FORMATS[fmt]
    sys_msg = persona_prefix(user_settings) + SYS_TEMPLATE.format(
        citation_instruction=cf["instruction"]
    )

    user_msg = (
        f"Paper title: {paper_title}\n"
        f"Chapter: {chapter_title}\n"
        f"Sub-chapter to write: {subchapter_title}\n\n"
        f"Citation format: {cf['label']} (example marker: {cf['example']})\n\n"
        f"Available fragments:\n{fragments_text}\n\n"
    )
    if previous_paragraph:
        user_msg += (
            "Previous paragraph (continue from this with a natural transition; do not repeat it):\n"
            f"\"{previous_paragraph}\"\n\n"
        )
    user_msg += (
        "Write 2-3 paragraphs for the sub-chapter. Use ONLY the fragments above. "
        "Every claim that comes from a fragment must end with a citation marker. "
        "Include the fragment id tag (e.g. [F3]) as instructed so we can resolve sources."
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
        # Re-raise as generic content with no badges so the UI doesn't crash
        return {
            "content_html": "<p><em>Model gagal menghasilkan JSON yang valid. Coba model lain atau ulangi.</em></p>",
            "plain_paragraphs": [],
            "badges": [],
            "references_used": [],
        }

    if not isinstance(data, dict):
        data = {}
    paragraphs = data.get("paragraphs") or []
    if not isinstance(paragraphs, list):
        paragraphs = []
    paragraphs = [str(p).strip() for p in paragraphs if str(p).strip()]

    # Parse fragment-id markers and replace with badge spans
    frag_pat = _fragment_id_re_for_format(fmt)
    frag_by_id = {f["frag_id"]: f for f in fragments}

    badges: List[Dict[str, Any]] = []
    used_doc_ids: set = set()
    doc_to_ieee_idx: Dict[str, int] = {}
    next_ieee = 1

    html_parts: List[str] = []
    for para in paragraphs:
        # We replace every match with a badge span
        def _sub(m: re.Match) -> str:
            nonlocal next_ieee
            num = m.group(1)
            frag_key = f"F{num}"
            frag = frag_by_id.get(frag_key)
            if not frag:
                return m.group(0)  # leave as-is

            doc_id = frag["doc_id"]
            # Compute display label per format
            if fmt == "ieee":
                if doc_id not in doc_to_ieee_idx:
                    doc_to_ieee_idx[doc_id] = next_ieee
                    next_ieee += 1
                label = _doc_label_ieee(doc_to_ieee_idx[doc_id])
            elif fmt == "apa7":
                label = _doc_label_apa(frag["authors"], frag["year"])
            else:  # harvard
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
            # Render as a non-editable span — frontend identifies via data-badge-id
            return (
                f'<span class="jm-citation-badge" data-badge-id="{badge_id}" '
                f'data-document-id="{doc_id}" data-sentence-id="{frag["sentence"]["id"]}" '
                f'data-page="{frag["sentence"].get("page","")}" '
                f'contenteditable="false">{label}</span>'
            )

        rendered = frag_pat.sub(_sub, para)
        # In APA/Harvard the model emits e.g. "(Smith, 2023) [F3]" — we already turned
        # "[F3]" into a badge but the leading "(Smith, 2023)" is still there. We replace
        # it with nothing only when followed immediately by a badge (cleaner reading).
        # For simplicity we keep it — both author-year and the [F3] badge act as a label.
        html_parts.append(f"<p>{rendered}</p>")

    refs_index: Dict[str, Dict[str, Any]] = {}
    for f in fragments:
        if f["doc_id"] in used_doc_ids and f["doc_id"] not in refs_index:
            refs_index[f["doc_id"]] = {
                "document_id": f["doc_id"],
                "title": f["doc_title"],
                "authors": f["authors"],
                "year": f["year"],
            }

    return {
        "content_html": "\n".join(html_parts) if html_parts else "<p></p>",
        "plain_paragraphs": paragraphs,
        "badges": badges,
        "references_used": list(refs_index.values()),
    }
