"""Orchestrates the full upload-to-ready pipeline for one document."""
from __future__ import annotations

import logging
import traceback
import uuid as _uuid
from typing import Any, Dict, Optional

from .pdf_parser import parse_pdf
from .summary_service import summarise_document

logger = logging.getLogger(__name__)


async def process_document(
    db,
    document_id: str,
    pdf_path: str,
    *,
    user_settings: Optional[Dict[str, Any]] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> None:
    """Background task: parse PDF -> insert sentences -> generate summary+claims."""
    try:
        parsed = parse_pdf(pdf_path)
        sentences = parsed["sentences"]

        sentence_docs = []
        for i, s in enumerate(sentences):
            sentence_docs.append({
                "id": str(_uuid.uuid4()),
                "document_id": document_id,
                "idx": i,
                **s,
            })

        if sentence_docs:
            await db.sentences.insert_many(sentence_docs)

        title = parsed.get("title") or ""
        summary_data = await summarise_document(
            document_id,
            title,
            sentences,
            user_settings=user_settings,
            provider=provider,
            model=model,
        )

        claim_docs = []
        for c in summary_data.get("claims", []):
            claim_docs.append({
                "id": str(_uuid.uuid4()),
                "document_id": document_id,
                "idx": c.get("idx", 0),
                "text": c.get("text", ""),
                "category": c.get("category", "finding"),
            })
        if claim_docs:
            await db.claims.insert_many(claim_docs)

        update_set = {
            "status": "ready",
            "page_count": parsed.get("page_count", 0),
            "title": title or None,
            "summary": summary_data.get("summary", ""),
            "sections": summary_data.get("sections", {}),
            "model_used": model,
            "persona_used": (user_settings or {}).get("persona_id"),
            "quality": parsed.get("quality") or {},
        }
        await db.documents.update_one({"id": document_id}, {"$set": update_set})
        logger.info("Document %s processed: %d sentences, %d claims",
                    document_id, len(sentence_docs), len(claim_docs))
    except Exception as e:
        logger.error("Failed to process %s: %s\n%s", document_id, e, traceback.format_exc())
        await db.documents.update_one(
            {"id": document_id},
            {"$set": {"status": "failed", "error": str(e)[:300]}},
        )


async def regenerate_summary(
    db,
    document_id: str,
    *,
    user_settings: Optional[Dict[str, Any]] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Re-run only the summarisation step using existing sentences."""
    doc = await db.documents.find_one({"id": document_id}, {"_id": 0})
    if not doc:
        raise ValueError("document not found")
    sentences = await db.sentences.find({"document_id": document_id}, {"_id": 0}).sort("idx", 1).to_list(5000)
    title = doc.get("title") or doc.get("filename") or ""

    summary_data = await summarise_document(
        document_id,
        title,
        sentences,
        user_settings=user_settings,
        provider=provider,
        model=model,
    )

    # replace claims
    await db.claims.delete_many({"document_id": document_id})
    claim_docs = []
    for c in summary_data.get("claims", []):
        claim_docs.append({
            "id": str(_uuid.uuid4()),
            "document_id": document_id,
            "idx": c.get("idx", 0),
            "text": c.get("text", ""),
            "category": c.get("category", "finding"),
        })
    if claim_docs:
        await db.claims.insert_many(claim_docs)

    await db.documents.update_one(
        {"id": document_id},
        {"$set": {
            "summary": summary_data.get("summary", ""),
            "sections": summary_data.get("sections", {}),
            "model_used": model,
            "persona_used": (user_settings or {}).get("persona_id"),
        }},
    )
    return {"summary": summary_data, "claim_ids": [c["id"] for c in claim_docs]}
