"""Lightweight BM25 retrieval over sentences (in-memory per request)."""
from __future__ import annotations

import re
from typing import List, Tuple, Dict, Any

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
