"""
Utility functions for the hybrid PDF parser.
"""
import uuid
from typing import Optional


def generate_uuid() -> str:
    """Generate a unique identifier."""
    return str(uuid.uuid4())


def normalize_bbox(bbox: list[float]) -> list[float]:
    """
    Normalize bounding box to [x0, y0, x1, y1] format.

    Ensures:
    - 4 float values
    - x0 <= x1, y0 <= y1
    """
    if not bbox or len(bbox) != 4:
        return [0.0, 0.0, 0.0, 0.0]

    x0, y0, x1, y1 = bbox
    return [
        min(x0, x1),
        min(y0, y1),
        max(x0, x1),
        max(y0, y1)
    ]


def normalize_page(page: int) -> int:
    """Ensure page number is 1-based and positive."""
    return max(1, page)


def jaccard_similarity(text_a: str, text_b: str) -> float:
    """
    Calculate Jaccard similarity between two text strings.

    Uses word-level set intersection over union.

    Args:
        text_a: First text.
        text_b: Second text.

    Returns:
        float: Similarity score between 0.0 and 1.0.
    """
    if not text_a or not text_b:
        return 0.0

    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())

    if not words_a or not words_b:
        return 0.0

    intersection = words_a & words_b
    union = words_a | words_b

    return len(intersection) / len(union)


def is_bbox_inside(
    inner_bbox: list[float],
    outer_bbox: list[float],
    tolerance: float = 2.0
) -> bool:
    """
    Check if inner_bbox is inside outer_bbox with tolerance.

    Uses the center point of the inner bbox for containment check.

    Args:
        inner_bbox: [x0, y0, x1, y1] of the inner object (e.g., word).
        outer_bbox: [x0, y0, x1, y1] of the outer object (e.g., block).
        tolerance: Pixel tolerance for boundary matching.

    Returns:
        bool: True if inner is inside outer.
    """
    if all(v == 0 for v in outer_bbox):
        return False
    if all(v == 0 for v in inner_bbox):
        return False

    cx = (inner_bbox[0] + inner_bbox[2]) / 2
    cy = (inner_bbox[1] + inner_bbox[3]) / 2

    return (
        (outer_bbox[0] - tolerance) <= cx <= (outer_bbox[2] + tolerance)
        and (outer_bbox[1] - tolerance) <= cy <= (outer_bbox[3] + tolerance)
    )