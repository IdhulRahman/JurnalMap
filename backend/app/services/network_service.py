"""Composite similarity network graph for Tab Baca.

Computes edges between documents using a weighted composite score:
  composite = 0.5 * semantic + 0.3 * keyword_jaccard + 0.2 * topic_match

- semantic: cosine similarity between document embeddings. Uses
  sentence-transformers if EMBEDDING_ENABLED is truthy and the model can be
  loaded, otherwise falls back to TF cosine (retrieval.doc_vector).
- keyword_jaccard: Jaccard similarity over the top-N keywords per document.
- topic_match: overlap of the top-5 dominant keywords per document.
"""
from __future__ import annotations

import logging
import math
import os
from typing import Any, Dict, List, Optional

from .retrieval import doc_vector, cosine, tokenize

logger = logging.getLogger(__name__)

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "and", "or", "but", "of", "in", "on", "at", "to", "for", "with", "by",
    "from", "as", "this", "that", "these", "those", "it", "its", "we",
    "our", "they", "their", "he", "she", "him", "her", "his", "you", "your",
    "i", "me", "my", "not", "no", "so", "than", "then", "such", "also",
    "have", "has", "had", "do", "does", "did", "can", "could", "would",
    "should", "may", "might", "will", "shall", "if", "while", "when",
    "where", "what", "which", "who", "how", "all", "any", "some", "more",
    "most", "other", "into", "about", "between", "over", "under",
    "yang", "dan", "atau", "tetapi", "namun", "untuk", "pada", "di", "ke",
    "dari", "dengan", "dalam", "oleh", "tidak", "adalah", "ini", "itu",
    "saya", "kami", "kita", "kamu", "anda", "mereka", "akan", "telah",
    "sudah", "juga", "jika", "agar", "supaya", "karena", "sehingga",
    "bahwa", "sebagai", "antara", "lebih", "paling", "sangat",
    "study", "studies", "paper", "article", "results", "result", "method",
    "methods", "found", "show", "shows", "showed", "based", "using",
    "use", "used", "one", "two", "three", "table", "figure", "et", "al",
}


# ── Embedding model (lazy singleton) ────────────────────────────────────────
_model = None
_model_load_attempted = False


def _embedding_enabled() -> bool:
    return os.environ.get("EMBEDDING_ENABLED", "true").lower() in ("1", "true", "yes")


def _embedding_model_name() -> str:
    return os.environ.get("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")


def _try_load_model():
    """Attempt to load sentence-transformers model. Returns model or None."""
    global _model, _model_load_attempted
    if _model_load_attempted:
        return _model
    _model_load_attempted = True
    if not _embedding_enabled():
        logger.info("Embedding disabled via EMBEDDING_ENABLED; using TF fallback")
        return None
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        model_name = _embedding_model_name()
        logger.info("Loading sentence-transformers model %s ...", model_name)
        _model = SentenceTransformer(model_name)
        logger.info("Loaded embedding model %s", model_name)
    except Exception as e:  # noqa: BLE001
        logger.warning("Embedding model unavailable, using TF cosine fallback: %s", e)
        _model = None
    return _model


# ── Keyword extraction (TF-IDF style) ────────────────────────────────────────

def _doc_text(sentences: List[Dict[str, Any]], max_chars: int = 12000) -> str:
    out, total = [], 0
    for s in sentences:
        t = s.get("text", "")
        if total + len(t) > max_chars:
            break
        out.append(t)
        total += len(t)
    return " ".join(out)


def _tf(sentences: List[Dict[str, Any]]) -> Dict[str, float]:
    tf: Dict[str, float] = {}
    for s in sentences:
        for tok in tokenize(s.get("text", "")):
            if len(tok) >= 4 and not tok.isdigit() and tok not in _STOPWORDS:
                tf[tok] = tf.get(tok, 0.0) + 1.0
    return tf


def _top_keywords(tf: Dict[str, float], k: int = 10) -> List[str]:
    items = sorted(tf.items(), key=lambda x: x[1], reverse=True)
    return [tok for tok, _ in items[:k]]


def _jaccard(a: List[str], b: List[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def _topic_match(a: List[str], b: List[str]) -> float:
    """Overlap of the top-5 keywords (as fraction of 5)."""
    sa, sb = set(a[:5]), set(b[:5])
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / 5.0


# ── Public entry point ───────────────────────────────────────────────────────

EDGE_THRESHOLD = 0.7
ISOLATED_THRESHOLD = 0.4


def compute_network(documents: List[Dict[str, Any]]) -> Dict[str, Any]:
    """documents: [{id, title, sentences}]. Returns {nodes, edges, summary, embedding_backend}."""
    if not documents:
        return {"nodes": [], "edges": [], "summary": "Tidak ada dokumen dalam proyek.", "embedding_backend": "none"}

    # Per-doc TF, keywords
    tfs = [_tf(d.get("sentences", [])) for d in documents]
    top_kws = [_top_keywords(tf, k=10) for tf in tfs]

    # Semantic vectors
    backend = "tf-cosine"
    sem_matrix: Optional[list] = None
    model = _try_load_model()
    if model is not None:
        try:
            texts = [_doc_text(d.get("sentences", [])) for d in documents]
            texts = [t if t.strip() else "empty" for t in texts]
            embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False, normalize_embeddings=True)
            # cosine similarity via dot product (normalized)
            n = len(embeddings)
            sem_matrix = [[float((embeddings[i] * embeddings[j]).sum()) for j in range(n)] for i in range(n)]
            backend = f"sentence-transformers ({_embedding_model_name()})"
        except Exception as e:  # noqa: BLE001
            logger.warning("Embedding encode failed, falling back to TF cosine: %s", e)
            sem_matrix = None

    if sem_matrix is None:
        # Fallback: TF cosine
        vectors = [doc_vector(d.get("sentences", [])) for d in documents]
        n = len(vectors)
        sem_matrix = [[cosine(vectors[i], vectors[j]) for j in range(n)] for i in range(n)]

    n = len(documents)

    # Build edges
    edges: List[Dict[str, Any]] = []
    # Track max composite for each node (to detect isolated nodes)
    max_score = [0.0] * n

    for i in range(n):
        for j in range(i + 1, n):
            sem = float(sem_matrix[i][j])
            keyword = _jaccard(top_kws[i], top_kws[j])
            topic = _topic_match(top_kws[i], top_kws[j])
            composite = 0.5 * sem + 0.3 * keyword + 0.2 * topic
            if composite > max_score[i]:
                max_score[i] = composite
            if composite > max_score[j]:
                max_score[j] = composite
            if composite >= EDGE_THRESHOLD:
                # keyword overlap tokens (top 3 shared)
                shared = list(set(top_kws[i][:8]) & set(top_kws[j][:8]))[:5]
                edges.append({
                    "source": documents[i]["id"],
                    "target": documents[j]["id"],
                    "weight": round(composite, 4),
                    "semantic": round(sem, 4),
                    "keyword": round(keyword, 4),
                    "topic": round(topic, 4),
                    "shared_keywords": shared,
                })

    # Nodes
    nodes: List[Dict[str, Any]] = []
    for i, d in enumerate(documents):
        isolated = max_score[i] < ISOLATED_THRESHOLD
        nodes.append({
            "id": d["id"],
            "title": d.get("title") or "Untitled",
            "keywords": top_kws[i][:6],
            "max_edge_score": round(max_score[i], 4),
            "isolated": isolated,
        })

    isolated_count = sum(1 for n_ in nodes if n_["isolated"])
    if len(documents) < 2:
        summary = "Perlu minimal 2 jurnal untuk membentuk graf."
    elif not edges:
        summary = "Tidak ditemukan hubungan kuat antar jurnal (composite < 0.70)."
    else:
        summary = f"{len(edges)} hubungan terbentuk dari {len(documents)} jurnal."
        if isolated_count:
            summary += f" {isolated_count} jurnal terisolasi (potensial tidak relevan)."

    return {
        "nodes": nodes,
        "edges": edges,
        "summary": summary,
        "embedding_backend": backend,
        "threshold": EDGE_THRESHOLD,
        "isolated_threshold": ISOLATED_THRESHOLD,
    }
