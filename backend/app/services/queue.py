"""Async single-worker PDF processing queue.

Design
------
- Documents are inserted with status='queued'.
- A single background asyncio task (started at app startup) polls the
  `documents` collection for the next queued item, atomically flips its
  status to 'processing', parses the PDF, stores sentences, then marks it
  'ready'. On error the doc is marked 'failed'.
- Concurrency is guaranteed to be 1 by design (single worker task).
- No Celery / Redis required. Persistent across restarts because the queue
  lives in MongoDB.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from pymongo import ASCENDING, ReturnDocument

from .document_processor import process_document_parse_only

logger = logging.getLogger(__name__)

_worker_task: Optional[asyncio.Task] = None
_stop_event: Optional[asyncio.Event] = None

POLL_INTERVAL = float(os.environ.get("QUEUE_POLL_INTERVAL", "1.5"))


async def _process_next(db, upload_dir: Path) -> bool:
    """Try to claim one queued doc and process it. Returns True if a doc was processed."""
    doc = await db.documents.find_one_and_update(
        {"status": "queued"},
        {"$set": {"status": "processing"}},
        sort=[("uploaded_at", ASCENDING)],
        return_document=ReturnDocument.AFTER,
    )
    if not doc:
        return False

    pdf_path = upload_dir / f"{doc['id']}.pdf"
    if not pdf_path.exists():
        logger.warning("Queue worker: missing file for %s", doc["id"])
        await db.documents.update_one(
            {"id": doc["id"]},
            {"$set": {"status": "failed", "error": "Uploaded file is missing on disk"}},
        )
        return True

    try:
        await process_document_parse_only(db, doc["id"], str(pdf_path))
    except Exception as e:  # noqa: BLE001
        logger.exception("Queue worker: failed to process %s", doc["id"])
        await db.documents.update_one(
            {"id": doc["id"]},
            {"$set": {"status": "failed", "error": str(e)[:300]}},
        )
    return True


async def _worker_loop(db, upload_dir: Path) -> None:
    logger.info("Queue worker started (poll=%ss)", POLL_INTERVAL)
    while _stop_event is not None and not _stop_event.is_set():
        try:
            worked = await _process_next(db, upload_dir)
            if not worked:
                await asyncio.sleep(POLL_INTERVAL)
        except asyncio.CancelledError:
            break
        except Exception:  # noqa: BLE001
            logger.exception("Queue worker loop error")
            await asyncio.sleep(POLL_INTERVAL)


def start_worker(db, upload_dir: Path) -> asyncio.Task:
    global _worker_task, _stop_event
    if _worker_task and not _worker_task.done():
        return _worker_task
    _stop_event = asyncio.Event()
    _worker_task = asyncio.create_task(_worker_loop(db, upload_dir), name="jurnalmap-queue")
    return _worker_task


async def stop_worker() -> None:
    global _worker_task, _stop_event
    if _stop_event is not None:
        _stop_event.set()
    if _worker_task is not None:
        _worker_task.cancel()
        try:
            await _worker_task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        _worker_task = None
        _stop_event = None


async def compute_queue_position(db, doc: dict) -> Optional[int]:
    """Return 1-based queue position for a doc (0 = processing now, None = not queued)."""
    status = doc.get("status")
    if status == "processing":
        return 0
    if status != "queued":
        return None
    ahead = await db.documents.count_documents({
        "status": {"$in": ["queued", "processing"]},
        "uploaded_at": {"$lt": doc.get("uploaded_at", "")},
    })
    return ahead + 1


async def queue_summary(db) -> dict:
    """Return { processing: N, queued: N, total: N } across the whole install."""
    processing = await db.documents.count_documents({"status": "processing"})
    queued = await db.documents.count_documents({"status": "queued"})
    return {"processing": processing, "queued": queued, "total": processing + queued}
