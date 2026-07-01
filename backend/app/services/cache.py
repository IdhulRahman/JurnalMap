"""In-memory cache for expensive computations.

Uses TTLCache from cachetools to avoid rebuilding BM25 indexes and
outlier calculations on every request.

Cache keys:
  bm25:<document_id>   → BM25Okapi index object (TTL: 30 min)
  outlier:<project_id> → outlier result dict   (TTL: 5 min)
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from cachetools import TTLCache

logger = logging.getLogger(__name__)

# BM25 indexes — 30 min TTL, max 200 documents cached
_BM25_CACHE: TTLCache = TTLCache(maxsize=200, ttl=1800)

# Outlier results — 5 min TTL, max 50 projects cached
_OUTLIER_CACHE: TTLCache = TTLCache(maxsize=50, ttl=300)


# ── BM25 ──────────────────────────────────────────────────────────────────────

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
    logger.debug("BM25 cache invalidated for doc %s", doc_id)


# ── Outlier ───────────────────────────────────────────────────────────────────

def get_outlier(project_id: str) -> Optional[dict]:
    """Return cached outlier result for a project, or None if not cached."""
    return _OUTLIER_CACHE.get(project_id)


def set_outlier(project_id: str, result: dict) -> None:
    """Store outlier computation result for a project."""
    _OUTLIER_CACHE[project_id] = result
    logger.debug("Outlier cached for project %s", project_id)


def invalidate_outlier(project_id: str) -> None:
    """Remove cached outlier for a project (call when docs change)."""
    _OUTLIER_CACHE.pop(project_id, None)
    logger.debug("Outlier cache invalidated for project %s", project_id)


def cache_stats() -> dict:
    """Return current cache stats for monitoring/debugging."""
    return {
        "bm25_entries": len(_BM25_CACHE),
        "bm25_maxsize": _BM25_CACHE.maxsize,
        "outlier_entries": len(_OUTLIER_CACHE),
        "outlier_maxsize": _OUTLIER_CACHE.maxsize,
    }
