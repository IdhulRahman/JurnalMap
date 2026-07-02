"""Shared sentence-embedding singleton for JurnalMap.

Provides a lazy-loaded SentenceTransformer model that is shared across
all services (retrieval, network graph, etc.) to avoid loading the model
multiple times into memory.

Usage:
    from .embedding import get_model, embed_texts, embed_one, is_enabled
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Lazy singleton ─────────────────────────────────────────────────────────────
_model = None
_model_load_attempted = False


def is_enabled() -> bool:
    """Return True if embedding is enabled via environment variable."""
    return os.environ.get("EMBEDDING_ENABLED", "true").lower() in ("1", "true", "yes")


def model_name() -> str:
    """Return the configured embedding model name."""
    return os.environ.get("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")


def get_model():
    """Return the SentenceTransformer model (lazy load, cached singleton).

    Returns None if:
    - EMBEDDING_ENABLED is falsy, OR
    - sentence-transformers is not installed, OR
    - model loading fails for any reason.
    """
    global _model, _model_load_attempted
    if _model_load_attempted:
        return _model
    _model_load_attempted = True
    if not is_enabled():
        logger.info("Embedding disabled via EMBEDDING_ENABLED; using BM25-only mode")
        return None
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        import torch  # type: ignore
        device = "cuda" if torch.cuda.is_available() else "cpu"
        name = model_name()
        logger.info("Loading sentence-transformers model '%s' on device '%s' ...", name, device)
        _model = SentenceTransformer(name, device=device)
        logger.info("Embedding model '%s' loaded successfully", name)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Embedding model unavailable (BM25-only fallback): %s", exc)
        _model = None
    return _model


def embed_texts(texts: List[str], batch_size: int = 128) -> Optional[np.ndarray]:
    """Encode a list of texts into a 2-D embedding matrix.

    Returns an ndarray of shape (len(texts), embedding_dim), or None if
    the model is unavailable or the input is empty.
    """
    if not texts:
        return None
    m = get_model()
    if m is None:
        return None
    try:
        vecs = m.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,  # L2-normalised → dot product == cosine
        )
        return vecs.astype(np.float32)
    except Exception as exc:  # noqa: BLE001
        logger.warning("embed_texts failed: %s", exc)
        return None


def embed_one(text: str) -> Optional[np.ndarray]:
    """Encode a single text into a 1-D embedding vector.

    Returns an ndarray of shape (embedding_dim,), or None if unavailable.
    """
    result = embed_texts([text])
    if result is None:
        return None
    return result[0]
