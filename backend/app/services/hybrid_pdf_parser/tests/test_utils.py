"""Tests for utility functions."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from hybrid_pdf_parser.utils import (
    normalize_bbox,
    normalize_page,
    jaccard_similarity,
    is_bbox_inside,
    generate_uuid
)


def test_generate_uuid():
    uid = generate_uuid()
    assert isinstance(uid, str)
    assert len(uid) > 0
    print("  [OK] generate_uuid")


def test_normalize_bbox():
    # Normal case
    assert normalize_bbox([100, 200, 500, 400]) == [100, 200, 500, 400]
    # Reversed coordinates
    assert normalize_bbox([500, 400, 100, 200]) == [100, 200, 500, 400]
    # Empty
    assert normalize_bbox([]) == [0, 0, 0, 0]
    # None
    assert normalize_bbox(None) == [0, 0, 0, 0]
    print("  [OK] normalize_bbox")


def test_normalize_page():
    assert normalize_page(1) == 1
    assert normalize_page(5) == 5
    assert normalize_page(0) == 1  # 0-based → 1-based
    assert normalize_page(-1) == 1
    print("  [OK] normalize_page")


def test_jaccard_similarity():
    # Identical
    assert jaccard_similarity("hello world", "hello world") == 1.0
    # Partial overlap
    score = jaccard_similarity("zero trust architecture", "zero trust model")
    assert 0.5 <= score <= 0.8
    # No overlap
    assert jaccard_similarity("abc", "xyz") == 0.0
    # Empty
    assert jaccard_similarity("", "hello") == 0.0
    print("  [OK] jaccard_similarity")


def test_is_bbox_inside():
    outer = [100, 100, 500, 500]
    # Inside
    assert is_bbox_inside([200, 200, 250, 250], outer) == True
    # Outside
    assert is_bbox_inside([600, 600, 650, 650], outer) == False
    # Zero bbox
    assert is_bbox_inside([0, 0, 0, 0], outer) == False
    assert is_bbox_inside([200, 200, 250, 250], [0, 0, 0, 0]) == False
    print("  [OK] is_bbox_inside")


if __name__ == "__main__":
    print("Testing utils...")
    test_generate_uuid()
    test_normalize_bbox()
    test_normalize_page()
    test_jaccard_similarity()
    test_is_bbox_inside()
    print("\nAll utils tests passed!")