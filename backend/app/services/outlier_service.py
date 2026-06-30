"""Outlier detection across documents in a project."""
from __future__ import annotations

from typing import List, Dict, Any
import math

from .retrieval import doc_vector, cosine


# Stopwords (English + Indonesian) used when extracting dominant keywords
_STOPWORDS = {
    # English
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "and", "or", "but", "of", "in", "on", "at", "to", "for", "with", "by",
    "from", "as", "this", "that", "these", "those", "it", "its", "we",
    "our", "they", "their", "he", "she", "him", "her", "his", "you", "your",
    "i", "me", "my", "not", "no", "so", "than", "then", "such", "also",
    "have", "has", "had", "do", "does", "did", "can", "could", "would",
    "should", "may", "might", "will", "shall", "if", "while", "when",
    "where", "what", "which", "who", "how", "all", "any", "some", "more",
    "most", "other", "into", "about", "between", "over", "under",
    # Indonesian
    "yang", "dan", "atau", "tetapi", "namun", "untuk", "pada", "di", "ke",
    "dari", "dengan", "dalam", "oleh", "tidak", "adalah", "ini", "itu",
    "saya", "kami", "kita", "kamu", "anda", "mereka", "akan", "telah",
    "sudah", "juga", "jika", "agar", "supaya", "karena", "sehingga",
    "bahwa", "sebagai", "antara", "lebih", "paling", "sangat",
    # Common in academic text
    "study", "studies", "paper", "article", "results", "result", "method",
    "methods", "found", "show", "shows", "showed", "based", "using",
    "use", "used", "one", "two", "three", "table", "figure", "et", "al",
}


def _dominant_keywords(tf: Dict[str, float], k: int = 6) -> List[str]:
    items = [
        (tok, w)
        for tok, w in tf.items()
        if len(tok) >= 4 and not tok.isdigit() and tok not in _STOPWORDS
    ]
    items.sort(key=lambda x: x[1], reverse=True)
    return [tok for tok, _ in items[:k]]


def compute_outliers(documents: List[Dict[str, Any]]) -> Dict[str, Any]:
    """documents: [{id, title, sentences: [...]}]. Returns {points, summary}."""
    if len(documents) == 0:
        return {"points": [], "summary": "Tidak ada dokumen dalam proyek."}

    # build TF vectors
    vectors = [doc_vector(d["sentences"]) for d in documents]
    n = len(documents)

    if n == 1:
        return {
            "points": [
                {
                    "document_id": documents[0]["id"],
                    "title": documents[0]["title"] or "Untitled",
                    "x": 0.5,
                    "y": 0.5,
                    "similarity_to_centroid": 1.0,
                    "is_outlier": False,
                    "keywords": _dominant_keywords(vectors[0]),
                }
            ],
            "summary": "Hanya satu dokumen, deteksi outlier butuh minimal 2.",
        }

    # mean similarity for each doc
    sims = []
    for i in range(n):
        s = 0.0
        for j in range(n):
            if i == j:
                continue
            s += cosine(vectors[i], vectors[j])
        sims.append(s / max(n - 1, 1))

    mean_sim = sum(sims) / n
    std_sim = math.sqrt(sum((x - mean_sim) ** 2 for x in sims) / n) if n > 1 else 0.0

    # 2D layout: simple MDS-ish. x = similarity to centroid; y = doc length normalised
    max_len = max((sum(1 for _ in d["sentences"]) for d in documents), default=1) or 1
    points = []
    for i, d in enumerate(documents):
        is_outlier = std_sim > 0 and sims[i] < mean_sim - 0.75 * std_sim
        x = sims[i]  # 0..1
        y = (len(d["sentences"]) / max_len) if max_len else 0.0
        points.append(
            {
                "document_id": d["id"],
                "title": d["title"] or "Untitled",
                "x": float(x),
                "y": float(y),
                "similarity_to_centroid": float(sims[i]),
                "is_outlier": bool(is_outlier),
                "keywords": _dominant_keywords(vectors[i]),
            }
        )

    outliers = [p for p in points if p["is_outlier"]]
    if outliers:
        names = ", ".join(p["title"][:40] for p in outliers)
        summary = (
            f"{len(outliers)} dokumen terdeteksi sebagai outlier (kosakata berbeda jauh dari rerata proyek): {names}. "
            "Ini bukan penilaian kualitas — pertimbangkan apakah dokumen tersebut relevan dengan topik proyek."
        )
    else:
        summary = "Tidak ada outlier terdeteksi. Semua dokumen memiliki kosakata yang relatif konsisten."
    return {"points": points, "summary": summary}
