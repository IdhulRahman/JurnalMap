"""Generate per-document summary + claims using Gemini."""
from __future__ import annotations

from typing import Any, Dict, List

from .llm import generate_json


SYSTEM = (
    "You are JurnalMap's evidence-finder. Your job is to extract structured information "
    "from a scientific journal article. You DO NOT judge whether claims are true. "
    "You only report what the paper says. Be neutral, concise, and faithful to the source. "
    "Respond in the same primary language as the article."
)


def _condense(sentences: List[Dict[str, Any]], max_chars: int = 14000) -> str:
    """Build a condensed source text, prioritising abstract + intro + results + discussion."""
    priority = {"abstract": 0, "introduction": 1, "results": 2, "discussion": 3, "conclusion": 4, "methods": 5, "other": 6, "references": 9}
    ordered = sorted(sentences, key=lambda s: (priority.get(s.get("section") or "other", 6), s.get("page", 0)))
    out, total = [], 0
    for s in ordered:
        t = s["text"]
        if total + len(t) > max_chars:
            break
        out.append(t)
        total += len(t)
    return " ".join(out)


async def summarise_document(document_id: str, title: str, sentences: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Return { summary: str, claims: [{idx, text, category}] }."""
    if not sentences:
        return {"summary": "Tidak ada teks yang dapat diekstrak dari dokumen ini.", "claims": []}

    source = _condense(sentences)
    user = (
        f"Title: {title or '(untitled)'}\n\n"
        f"Article text (condensed, possibly out of order by section):\n---\n{source}\n---\n\n"
        "Produce a JSON object with this exact shape:\n"
        "{\n"
        '  "summary": "<2-3 sentence neutral summary of what the article reports>",\n'
        '  "claims": [\n'
        '    {"idx": 0, "text": "<single concise claim, max 30 words>", "category": "objective|method|finding|limitation"},\n'
        '    ...\n'
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- Produce between 5 and 8 claims.\n"
        "- One claim per item, atomic and verifiable against the source.\n"
        "- Distribute categories: at least one objective, one method, multiple findings, one limitation if present.\n"
        "- Do NOT invent information not in the article. If unsure, omit the claim.\n"
        "- Write in the same language as the article (Indonesian or English)."
    )

    data = await generate_json(f"sum-{document_id}", SYSTEM, user)
    if not isinstance(data, dict):
        data = {"summary": "", "claims": []}
    claims = data.get("claims") or []
    # normalise
    norm_claims = []
    for i, c in enumerate(claims):
        if not isinstance(c, dict):
            continue
        text = (c.get("text") or "").strip()
        if not text:
            continue
        norm_claims.append(
            {
                "idx": int(c.get("idx", i)),
                "text": text,
                "category": (c.get("category") or "finding").lower(),
            }
        )
    return {"summary": (data.get("summary") or "").strip(), "claims": norm_claims}
