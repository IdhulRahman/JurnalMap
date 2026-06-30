"""Cross-document Q&A — Tanya Pustaka."""
from __future__ import annotations

from typing import List, Dict, Any
import uuid

from .llm import generate_json
from .retrieval import build_bm25, top_k


SYSTEM = (
    "You are JurnalMap's literature assistant. You answer questions strictly based on "
    "the provided excerpts from multiple journal articles. You ALWAYS cite the source "
    "by ID (S0, S1, ...). If the excerpts are insufficient, say so plainly. You report "
    "evidence; you do not judge truth. Respond in the same language as the question."
)


async def answer_question(
    question: str,
    documents: List[Dict[str, Any]],
    top_per_doc: int = 4,
    max_total: int = 12,
) -> Dict[str, Any]:
    """documents: [{id, title, sentences:[{id,text,page,...}]}]."""
    # Gather top-K per doc, then merge by score
    gathered: List[Dict[str, Any]] = []
    for d in documents:
        if not d["sentences"]:
            continue
        bm25 = build_bm25(d["sentences"])
        for sent, score in top_k(bm25, d["sentences"], question, k=top_per_doc):
            gathered.append({
                "doc_id": d["id"],
                "doc_title": d["title"] or "Untitled",
                "sentence": sent,
                "score": score,
            })
    gathered.sort(key=lambda x: x["score"], reverse=True)
    gathered = [g for g in gathered if g["score"] > 0][:max_total]

    if not gathered:
        return {
            "question": question,
            "answer": "Tidak ditemukan fragmen relevan di pustaka Anda untuk pertanyaan ini.",
            "citations": [],
            "overall_tier": "low",
        }

    excerpts_str = "\n".join(
        f'S{i}. [Doc: {g["doc_title"][:60]}, p.{g["sentence"]["page"]}] "{g["sentence"]["text"]}"'
        for i, g in enumerate(gathered)
    )
    user = (
        f"Question: {question}\n\n"
        f"Excerpts:\n{excerpts_str}\n\n"
        "Respond with JSON:\n"
        "{\n"
        '  "answer": "<answer that cites sources inline as [S0], [S2], ...>",\n'
        '  "used_sources": [\n'
        '    {"id": "S0", "tier": "high|medium|low"},\n'
        "    ...\n"
        "  ],\n"
        '  "overall_tier": "high|medium|low"\n'
        "}\n"
        "Rules: only cite S-ids you actually used. tier high = excerpt directly answers question; "
        "medium = partial / requires inference; low = weak. If excerpts insufficient, say so and set overall_tier=low."
    )

    try:
        data = await generate_json(f"qa-{uuid.uuid4().hex[:8]}", SYSTEM, user)
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}

    used = data.get("used_sources") or []
    tier_map = {}
    for u in used:
        if isinstance(u, dict) and isinstance(u.get("id"), str):
            tier_map[u["id"]] = (u.get("tier") or "medium").lower()

    citations = []
    for i, g in enumerate(gathered):
        sid = f"S{i}"
        if sid in tier_map:
            citations.append({
                "document_id": g["doc_id"],
                "document_title": g["doc_title"],
                "sentence_id": g["sentence"]["id"],
                "page": g["sentence"]["page"],
                "excerpt": g["sentence"]["text"],
                "tier": tier_map[sid] if tier_map[sid] in ("high", "medium", "low") else "medium",
            })

    overall = (data.get("overall_tier") or "medium").lower()
    if overall not in ("high", "medium", "low"):
        overall = "medium"

    answer_text = (data.get("answer") or "").strip() or "Tidak ada jawaban yang dapat disusun."

    # Fallback: model returned an answer but forgot to list used_sources.
    # Without citations, the verify-by-click flow is broken — attach the top-3 BM25
    # fragments and flag the answer as not directly verified by the model.
    if not citations and gathered:
        fallback_notice = (
            "Sumber tidak terverifikasi langsung oleh model — "
            "ditampilkan 3 fragmen paling relevan dari hasil pencarian.\n\n"
        )
        answer_text = fallback_notice + answer_text
        for i, g in enumerate(gathered[:3]):
            citations.append({
                "document_id": g["doc_id"],
                "document_title": g["doc_title"],
                "sentence_id": g["sentence"]["id"],
                "page": g["sentence"]["page"],
                "excerpt": g["sentence"]["text"],
                "tier": "low",
            })
        overall = "low"

    return {
        "question": question,
        "answer": answer_text,
        "citations": citations,
        "overall_tier": overall,
    }
