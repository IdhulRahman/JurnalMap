"""Find evidence in a document for a given claim. Returns tiered highlights."""
from __future__ import annotations

from typing import List, Dict, Any

from .llm import generate_json
from .retrieval import build_bm25, top_k


SYSTEM = (
    "You are JurnalMap's evidence tracker. Given a CLAIM and a list of CANDIDATE sentences "
    "from a scientific paper, decide for each candidate whether it SUPPORTS the claim. "
    "You report evidence; you do not judge truth. Be strict: explicit support = high, "
    "implicit/related = medium, unrelated = low. Respond in the same language as the claim."
)


async def find_evidence(claim_text: str, sentences: List[Dict[str, Any]], k: int = 5) -> List[Dict[str, Any]]:
    """Return list of evidence items with tier (high/medium/low), score, rationale.

    sentences items must have keys: id, text, page, x0, y0, x1, y1, page_width, page_height.
    """
    if not sentences:
        return []
    bm25 = build_bm25(sentences)
    top = top_k(bm25, sentences, claim_text, k=k)
    if not top:
        return []

    candidates_payload = [
        {"idx": i, "text": s["text"]}
        for i, (s, _score) in enumerate(top)
    ]

    user = (
        f"CLAIM: {claim_text}\n\n"
        f"CANDIDATES (numbered):\n"
        + "\n".join(f'{c["idx"]}. {c["text"]}' for c in candidates_payload)
        + "\n\nRespond with a JSON array. One entry per candidate, in the same order:\n"
        '[\n  {"idx": 0, "tier": "high|medium|low", "rationale": "<one short clause>"},\n  ...\n]\n'
        "Rules:\n"
        "- high: candidate explicitly states (or paraphrases closely) the claim.\n"
        "- medium: candidate is topically related or partially supports.\n"
        "- low: candidate is unrelated or contradicts.\n"
        "- Rationale must be short (max 12 words)."
    )

    try:
        verdicts = await generate_json(f"ev-{claim_text[:32]}", SYSTEM, user)
    except Exception:
        verdicts = []
    if not isinstance(verdicts, list):
        verdicts = []
    verdict_map = {int(v.get("idx", -1)): v for v in verdicts if isinstance(v, dict)}

    results: List[Dict[str, Any]] = []
    for i, (s, bm25_score) in enumerate(top):
        v = verdict_map.get(i) or {}
        tier = (v.get("tier") or "").lower()
        if tier not in ("high", "medium", "low"):
            # fallback heuristic based on BM25 score
            if bm25_score >= 8:
                tier = "high"
            elif bm25_score >= 3:
                tier = "medium"
            else:
                tier = "low"
        results.append(
            {
                "sentence_id": s["id"],
                "page": s["page"],
                "x0": s["x0"],
                "y0": s["y0"],
                "x1": s["x1"],
                "y1": s["y1"],
                "page_width": s["page_width"],
                "page_height": s["page_height"],
                "text": s["text"],
                "tier": tier,
                "score": float(bm25_score),
                "rationale": (v.get("rationale") or "").strip()[:120],
            }
        )
    # only keep medium/high in highlights, but still return low for completeness
    return results
