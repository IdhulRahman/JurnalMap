"""Comparison matrix across multiple journals.

Supports multiple comparison methods (see app.models.schemas.MATRIX_METHODS):
- default            Tujuan/Metode/Sampel/Temuan/Keterbatasan
- gap_analysis       What is known / Gap / Why unresolved / Opportunity
- method_comparison  Study design / Sampling / Data collection / Analysis / Validity
- feature_comparison Features / Dataset / Evaluation metric / Performance
- experimental_comparison  Hypothesis / Conditions / Controls / Results / Statistical test
"""
from __future__ import annotations

from typing import Any, Dict, List

from .llm import generate_json, persona_prefix
from .summary_service import _condense
from app.models.schemas import MATRIX_METHODS


BASE_SYSTEM = (
    "You are JurnalMap's comparison assistant. You extract structured fields from a journal "
    "to enable side-by-side comparison. You do NOT decide which paper is better. You only "
    "report what is in the text. If a field is not present, return 'tidak disebutkan'."
)


def fields_for(method: str) -> list[str]:
    return list(MATRIX_METHODS.get(method, MATRIX_METHODS["default"])["fields"])


def _user_prompt(title: str, source: str, fields: list[str]) -> str:
    field_lines = "\n".join(
        f'  "{f}": {{"value": "<short>", "excerpt": "<verbatim quote from source>", "page": <int or null>}},'
        for f in fields
    )
    return (
        f"Title: {title or '(untitled)'}\n\n"
        f"Article text:\n---\n{source}\n---\n\n"
        "Extract the following fields as a JSON object:\n"
        "{\n"
        + field_lines.rstrip(",")
        + "\n}\n"
        'Use "tidak disebutkan" for missing fields. Excerpt should quote the source as closely as possible. '
        "Respond in the language requested by your system message."
    )


async def extract_row(
    document_id: str,
    title: str,
    sentences,
    *,
    user_settings=None,
    provider=None,
    model=None,
    method: str = "default",
):
    if not sentences:
        return {"document_id": document_id, "title": title or "Untitled", "cells": []}

    fields = fields_for(method)
    source = _condense(sentences, max_chars=10000)
    user = _user_prompt(title, source, fields)

    data = await generate_json(
        f"mat-{document_id}-{method}",
        persona_prefix(user_settings) + BASE_SYSTEM,
        user,
        provider=provider,
        model=model,
        user_settings=user_settings,
    )
    if not isinstance(data, dict):
        data = {}
    cells = []
    for field in fields:
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
