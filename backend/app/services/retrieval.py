"""Lightweight BM25 retrieval + Hybrid RRF retrieval over sentences (in-memory per request)."""
from __future__ import annotations

import re
from typing import List, Tuple, Dict, Any, Optional

import numpy as np
from rank_bm25 import BM25Okapi


_TOKEN = re.compile(r"[A-Za-z0-9]+")


def tokenize(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN.findall(text or "") if len(t) > 1]


def build_bm25(sentences: List[Dict[str, Any]]) -> BM25Okapi:
    corpus = [tokenize(s["text"]) for s in sentences]
    if not corpus or all(len(c) == 0 for c in corpus):
        # avoid div-by-zero in BM25 — seed dummy token
        corpus = [["empty"] for _ in sentences] if sentences else [["empty"]]
    return BM25Okapi(corpus)


def top_k(
    bm25: BM25Okapi,
    sentences: List[Dict[str, Any]],
    query: str,
    k: int = 5,
) -> List[Tuple[Dict[str, Any], float]]:
    if not sentences:
        return []
    scores = bm25.get_scores(tokenize(query))
    # take top-k indices
    idxs = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
    return [(sentences[i], float(scores[i])) for i in idxs if scores[i] > 0]


def doc_vector(sentences: List[Dict[str, Any]]) -> Dict[str, float]:
    """Simple TF vector for a whole document (for outlier detection)."""
    tf: Dict[str, float] = {}
    for s in sentences:
        for tok in tokenize(s["text"]):
            tf[tok] = tf.get(tok, 0.0) + 1.0
    total = sum(tf.values()) or 1.0
    return {k: v / total for k, v in tf.items()}


def cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    keys = set(a) | set(b)
    if not keys:
        return 0.0
    dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in keys)
    na = sum(v * v for v in a.values()) ** 0.5
    nb = sum(v * v for v in b.values()) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ── Hybrid Retrieval (Semantic + RRF) ─────────────────────────────────────────

def semantic_top_k(
    query: str,
    sentences: List[Dict[str, Any]],
    k: int = 5,
) -> List[Tuple[Dict[str, Any], float]]:
    """Semantic retrieval using pre-stored sentence embeddings (cosine similarity).

    Sentences must have an 'embedding' field (list[float]) stored from indexing.
    Returns list of (sentence_dict, cosine_score) sorted by score descending.
    Falls back to empty list if embeddings are unavailable.
    """
    from .embedding import embed_one  # lazy import to avoid circular deps

    if not sentences:
        return []

    # Filter only sentences that have stored embeddings
    indexed = [(i, s) for i, s in enumerate(sentences) if s.get("embedding")]
    if not indexed:
        return []

    query_vec = embed_one(query)
    if query_vec is None:
        return []

    # Stack stored embeddings into matrix
    try:
        idxs, sents = zip(*indexed)
        matrix = np.array([s["embedding"] for s in sents], dtype=np.float32)
        # L2 normalise query (stored embeddings already normalised at index time)
        norm = np.linalg.norm(query_vec)
        if norm > 0:
            query_vec = query_vec / norm
        scores = matrix @ query_vec  # dot product == cosine for normalised vecs
    except Exception:
        return []

    top_positions = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
    return [(sentences[idxs[p]], float(scores[p])) for p in top_positions if scores[p] > 0]


def rrf_top_k(
    bm25: BM25Okapi,
    sentences: List[Dict[str, Any]],
    query: str,
    k: int = 5,
    rrf_k: int = 60,
    bm25_weight: float = 0.5,
    semantic_weight: float = 0.5,
) -> List[Tuple[Dict[str, Any], float]]:
    """Hybrid retrieval: BM25 + Semantic Search fused with Reciprocal Rank Fusion (RRF).

    RRF score for each sentence:
        score = bm25_weight / (rrf_k + rank_bm25)
              + semantic_weight / (rrf_k + rank_semantic)

    Falls back transparently to BM25-only when:
    - The embedding model is not available, OR
    - No sentence in the corpus has a stored 'embedding' field.
    """
    if not sentences:
        return []

    # ── BM25 ranking ──────────────────────────────────────────────────────────
    bm25_scores = bm25.get_scores(tokenize(query))
    bm25_order = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)
    bm25_rank = {idx: rank for rank, idx in enumerate(bm25_order)}  # idx → 0-based rank

    # ── Semantic ranking (optional) ───────────────────────────────────────────
    has_embeddings = any(s.get("embedding") for s in sentences)
    semantic_rank: Dict[int, int] = {}

    if has_embeddings:
        sem_results = semantic_top_k(query, sentences, k=len(sentences))
        if sem_results:
            # Map sentence id → rank
            id_to_idx = {s.get("id", i): i for i, s in enumerate(sentences)}
            for rank, (sent, _score) in enumerate(sem_results):
                sent_idx = id_to_idx.get(sent.get("id"), -1)
                if sent_idx >= 0:
                    semantic_rank[sent_idx] = rank

    # ── RRF Fusion ────────────────────────────────────────────────────────────
    rrf_scores: Dict[int, float] = {}
    for i in range(len(sentences)):
        bm25_r = bm25_rank.get(i, len(sentences))  # unranked → worst rank
        score = bm25_weight / (rrf_k + bm25_r)
        if semantic_rank:
            sem_r = semantic_rank.get(i, len(sentences))  # unranked → worst rank
            score += semantic_weight / (rrf_k + sem_r)
        rrf_scores[i] = score

    top_idxs = sorted(rrf_scores.keys(), key=lambda i: rrf_scores[i], reverse=True)[:k]
    # Only return sentences with positive BM25 score OR positive semantic score
    results = []
    for i in top_idxs:
        if bm25_scores[i] > 0 or i in semantic_rank:
            results.append((sentences[i], rrf_scores[i]))
    return results

