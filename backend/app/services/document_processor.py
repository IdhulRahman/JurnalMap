"""Orchestrates the full upload-to-ready pipeline for one document."""
from __future__ import annotations

import logging
import traceback
import uuid as _uuid
from typing import Any, Dict, List, Optional

from .pdf_parser import parse_pdf
from .summary_service import summarise_document
from .embedding import embed_texts, is_enabled as embedding_enabled
from .cache import invalidate_embeddings

logger = logging.getLogger(__name__)

_EMBED_BATCH = 128  # sentences per embedding batch


async def _embed_and_store(db, document_id: str, sentence_docs: List[Dict[str, Any]]) -> int:
    """Generate embeddings for sentence_docs and persist them to db.sentences.

    Works in batches of _EMBED_BATCH to avoid OOM on large documents.
    Returns the number of sentences successfully embedded.
    Silently skips if the embedding model is unavailable.
    """
    if not embedding_enabled() or not sentence_docs:
        return 0

    texts = [s["text"] for s in sentence_docs]
    ids = [s["id"] for s in sentence_docs]

    embedded_count = 0
    for batch_start in range(0, len(texts), _EMBED_BATCH):
        batch_texts = texts[batch_start: batch_start + _EMBED_BATCH]
        batch_ids = ids[batch_start: batch_start + _EMBED_BATCH]
        vecs = embed_texts(batch_texts, batch_size=_EMBED_BATCH)
        if vecs is None:
            break  # model unavailable — stop early
        # Bulk update sentences with their embedding vectors
        from motor.motor_asyncio import AsyncIOMotorDatabase  # type: ignore  # noqa
        from pymongo import UpdateOne  # type: ignore
        ops = [
            UpdateOne(
                {"id": sid},
                {"$set": {"embedding": vec.tolist()}},
            )
            for sid, vec in zip(batch_ids, vecs)
        ]
        await db.sentences.bulk_write(ops, ordered=False)
        embedded_count += len(batch_ids)

    # Invalidate embedding cache so next query re-loads from DB
    invalidate_embeddings(document_id)
    logger.info(
        "Embedded %d/%d sentences for document %s",
        embedded_count, len(sentence_docs), document_id,
    )
    return embedded_count



async def process_document_parse_only(
    db,
    document_id: str,
    pdf_path: str,
) -> None:
    """Queue worker task: parse PDF -> insert sentences. NO summary/claims.

    Status transitions:  processing -> ready (or failed).
    Summary is built on demand via /documents/{id}/summarize.
    """
    try:
        parsed = parse_pdf(pdf_path)
        sentences = parsed["sentences"]

        # Clear any previous sentences in case of a retry
        await db.sentences.delete_many({"document_id": document_id})
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
            # Generate and persist embeddings (non-blocking fallback if unavailable)
            try:
                await _embed_and_store(db, document_id, sentence_docs)
            except Exception as emb_err:  # noqa: BLE001
                logger.warning("Embedding generation skipped for %s: %s", document_id, emb_err)

        title = parsed.get("title") or ""
        update_set = {
            "status": "ready",
            "page_count": parsed.get("page_count", 0),
            "quality": parsed.get("quality") or {},
            # Clear any previous error / stale summary from a prior run
            "error": None,
            "summary": None,
            "sections": None,
            "model_used": None,
            "persona_used": None,
            "summary_language": None,
        }
        if title:
            update_set["title"] = title
        # Remove old claims (if this was a retry after a summary was built)
        await db.claims.delete_many({"document_id": document_id})

        await db.documents.update_one({"id": document_id}, {"$set": update_set})
        logger.info(
            "Document %s parsed: %d sentences (title=%s)",
            document_id, len(sentence_docs), title[:60] if title else "-",
        )
    except Exception as e:
        logger.error("Failed to parse %s: %s\n%s", document_id, e, traceback.format_exc())
        await db.documents.update_one(
            {"id": document_id},
            {"$set": {"status": "failed", "error": str(e)[:300]}},
        )


async def process_document(
    db,
    document_id: str,
    pdf_path: str,
    *,
    user_settings: Optional[Dict[str, Any]] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> None:
    """Legacy full pipeline: parse + summarise. Kept for compatibility with
    tests / callers that expect the previous behavior. Prefer
    `process_document_parse_only` + on-demand `regenerate_summary`.
    """
    await process_document_parse_only(db, document_id, pdf_path)
    doc = await db.documents.find_one({"id": document_id}, {"_id": 0})
    if doc and doc.get("status") == "ready":
        try:
            await regenerate_summary(
                db,
                document_id,
                user_settings=user_settings,
                provider=provider,
                model=model,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Auto-summary failed for %s: %s", document_id, e)


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
