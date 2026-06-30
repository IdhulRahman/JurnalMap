"""Comparison matrix across multiple journals."""
from __future__ import annotations

from typing import List, Dict, Any

from .llm import generate_json, persona_prefix
from .summary_service import _condense


BASE_SYSTEM = (
    "You are JurnalMap's comparison assistant. You extract structured fields from a journal "
    "to enable side-by-side comparison. You do NOT decide which paper is better. You only "
    "report what is in the text. If a field is not present, return 'tidak disebutkan'."
)

DEFAULT_FIELDS = [
    "objective",
    "method",
    "sample",
    "key_finding",
    "limitation",
]


async def extract_row(
    document_id: str,
    title: str,
    sentences,
    *,
    user_settings=None,
    provider=None,
    model=None,
):
    if not sentences:
        return {"document_id": document_id, "title": title or "Untitled", "cells": []}

    source = _condense(sentences, max_chars=10000)
    user = (
        f"Title: {title or '(untitled)'}\n\n"
        f"Article text:\n---\n{source}\n---\n\n"
        "Extract the following fields as a JSON object:\n"
        "{\n"
        '  "objective": {"value": "<short>", "excerpt": "<the exact sentence from the source>", "page": <int or null>},\n'
        '  "method":    {"value": "<short>", "excerpt": "...", "page": null},\n'
        '  "sample":    {"value": "<n, population>", "excerpt": "...", "page": null},\n'
        '  "key_finding": {"value": "<short>", "excerpt": "...", "page": null},\n'
        '  "limitation": {"value": "<short>", "excerpt": "...", "page": null}\n'
        "}\n"
        'Use "tidak disebutkan" for missing fields. Excerpt should quote the source as closely as possible. '
        "Respond in the same language as the article."
    )

    data = await generate_json(
        f"mat-{document_id}",
        persona_prefix(user_settings) + BASE_SYSTEM,
        user,
        provider=provider,
        model=model,
        user_settings=user_settings,
    )
    if not isinstance(data, dict):
        data = {}
    cells = []
    for field in DEFAULT_FIELDS:
        entry = data.get(field) or {}
        if isinstance(entry, str):
            entry = {"value": entry}
        cells.append(
            {
                "field": field,
                "value": (entry.get("value") or "tidak disebutkan").strip(),
                "excerpt": (entry.get("excerpt") or "").strip() or None,
                "page": entry.get("page") if isinstance(entry.get("page"), int) else None,
            }
        )
    return {"document_id": document_id, "title": title or "Untitled", "cells": cells}
