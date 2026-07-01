"""In-memory cache for expensive computations.

Uses TTLCache from cachetools to avoid rebuilding BM25 indexes on every request.

Cache keys:
  bm25:<document_id>   → BM25Okapi index object (TTL: 30 min)
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from cachetools import TTLCache

logger = logging.getLogger(__name__)

# BM25 indexes — 30 min TTL, max 200 documents cached
_BM25_CACHE: TTLCache = TTLCache(maxsize=200, ttl=1800)


# ── BM25 ────────────────------------------------------------------------------

def get_bm25(doc_id: str) -> Optional[Any]:
    """Return cached BM25 index for a document, or None if not cached."""
    return _BM25_CACHE.get(doc_id)


def set_bm25(doc_id: str, index: Any) -> None:
    """Store a BM25 index for a document in the cache."""
    _BM25_CACHE[doc_id] = index
    logger.debug("BM25 cached for doc %s (cache size: %d)", doc_id, len(_BM25_CACHE))


def invalidate_bm25(doc_id: str) -> None:
    """Remove cached BM25 index for a document (call when doc is updated/deleted)."""
    _BM25_CACHE.pop(doc_id, None)
    logger.debug("BM25 cache invalidated for doc %s")


def cache_stats() -> dict:
    """Return current cache stats for monitoring/debugging."""
    return {
        "bm25_entries": len(_BM25_CACHE),
        "bm25_maxsize": _BM25_CACHE.maxsize,
    }
