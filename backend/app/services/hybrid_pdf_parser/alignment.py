"""
Alignment Engine - Core research contribution.

Aligns word-level spatial data with block-level semantic data through
a two-phase alignment process:

Phase 1 - Spatial Alignment (Bounding Box Containment):
    Match words to spatial blocks using geometric containment.
    Both words and spatial blocks come from PyMuPDF, so their
    coordinate systems are identical.

Phase 2 - Semantic Alignment (Text Similarity):
    Bridge spatial blocks to semantic blocks using text content similarity.
    Since pymupdf4llm blocks have no bounding boxes, we match them
    to spatial blocks by comparing their text content using Jaccard similarity.

The alignment engine is independent of both parsers. It only works with
normalized DocumentObjects.
"""
from __future__ import annotations
from typing import Callable, Optional
from .normalization import DocumentObject
from .utils import is_bbox_inside, jaccard_similarity
from .exceptions import AlignmentError


class Aligner:
    """
    Two-phase alignment engine.

    Phase 1: Words → Spatial Blocks (bbox containment)
    Phase 2: Spatial Blocks → Semantic Blocks (text similarity)

    The similarity function can be injected for extensibility.
    """

    def __init__(
        self,
        similarity_fn: Optional[Callable[[str, str], float]] = None,
        similarity_threshold: float = 0.2,
        bbox_tolerance: float = 2.0
    ):
        """
        Initialize the aligner.

        Args:
            similarity_fn: Custom similarity function (default: Jaccard).
            similarity_threshold: Minimum similarity score to consider a match (0.0-1.0).
            bbox_tolerance: Pixel tolerance for bbox containment check.
        """
        self._similarity_fn = similarity_fn or jaccard_similarity
        self._similarity_threshold = similarity_threshold
        self._bbox_tolerance = bbox_tolerance

    def align(self, objects: list[DocumentObject], page_dimensions: dict[int, tuple[float, float]] = None) -> list[dict]:
        """
        Run the full alignment pipeline.

        Args:
            objects: List of normalized DocumentObjects from all parsers.
            page_dimensions: Optional dictionary of page_num -> (width, height)

        Returns:
            list[dict]: Per-page alignment results.
                Each entry: {
                    "page": int,
                    "width": float,
                    "height": float,
                    "aligned": [
                        {
                            "spatial_block": DocumentObject,
                            "words": [DocumentObject, ...],
                            "semantic_type": str or None,
                            "markdown_content": str or None
                        },
                        ...
                    ]
                }
        """
        # Group by page
        pages = self._group_by_page(objects)

        results = []
        for page_num in sorted(pages.keys()):
            page_objects = pages[page_num]

            # Separate by type
            words = [o for o in page_objects if o.type == "word"]
            spatial_blocks = [o for o in page_objects if o.type == "spatial_block"]
            semantic_blocks = [o for o in page_objects
                               if o.type not in ("word", "spatial_block")]

            # Phase 1: Spatial alignment
            spatial_aligned = self._spatial_align(spatial_blocks, words)

            # Phase 2: Semantic alignment
            final_aligned = self._semantic_align(spatial_aligned, semantic_blocks)

            # Sort by reading order
            final_aligned = self._sort_by_reading_order(final_aligned)

            # Get page dimensions
            width, height = 0.0, 0.0
            if page_dimensions and page_num in page_dimensions:
                width, height = page_dimensions[page_num]
            elif spatial_blocks:
                bbox = spatial_blocks[0].bbox
                width = bbox[2] - bbox[0]
                height = bbox[3] - bbox[1]

            results.append({
                "page": page_num,
                "width": width,
                "height": height,
                "aligned": final_aligned
            })

        return results

    def _group_by_page(
        self, objects: list[DocumentObject]
    ) -> dict[int, list[DocumentObject]]:
        """Group objects by page number."""
        pages: dict[int, list[DocumentObject]] = {}
        for obj in objects:
            page = obj.page
            if page not in pages:
                pages[page] = []
            pages[page].append(obj)
        return pages

    def _spatial_align(
        self,
        spatial_blocks: list[DocumentObject],
        words: list[DocumentObject]
    ) -> list[dict]:
        """
        Phase 1: Spatial Alignment.

        Match words to spatial blocks using bounding box containment.
        Both come from PyMuPDF, so coordinates are in the same space.

        Returns:
            list[dict]: Each entry: {"spatial_block": DocumentObject, "words": [...]}
        """
        aligned = []

        for block in spatial_blocks:
            matching_words = []
            for word in words:
                if is_bbox_inside(word.bbox, block.bbox, self._bbox_tolerance):
                    matching_words.append(word)

            aligned.append({
                "spatial_block": block,
                "words": matching_words
            })

        return aligned

    def _semantic_align(
        self,
        spatial_aligned: list[dict],
        semantic_blocks: list[DocumentObject]
    ) -> list[dict]:
        """
        Phase 2: Semantic Alignment.

        Bridge spatial blocks to semantic blocks using text similarity.
        Each spatial block is matched to the most similar semantic block.

        Unmatched semantic blocks are appended as standalone entries.
        """
        # Build text index for semantic blocks
        semantic_index = []
        for sem in semantic_blocks:
            sem_text = sem.content[:200].strip().lower() if sem.content else ""
            semantic_index.append({
                "obj": sem,
                "text": sem_text
            })

        result = []
        used_semantic: set[int] = set()

        for entry in spatial_aligned:
            block = entry["spatial_block"]
            block_text = block.content[:200].strip().lower() if block.content else ""

            # Find best matching semantic block
            best_idx = None
            best_score = 0.0

            for idx, sem_entry in enumerate(semantic_index):
                if idx in used_semantic:
                    continue
                if not sem_entry["text"] or not block_text:
                    continue

                score = self._similarity_fn(block_text, sem_entry["text"])
                if score > best_score and score >= self._similarity_threshold:
                    best_score = score
                    best_idx = idx

            aligned_entry = {
                "spatial_block": block,
                "words": entry["words"],
                "semantic_type": None,
                "markdown_content": None
            }

            if best_idx is not None:
                sem_obj = semantic_index[best_idx]["obj"]
                aligned_entry["semantic_type"] = sem_obj.type
                aligned_entry["markdown_content"] = sem_obj.content
                used_semantic.add(best_idx)

            result.append(aligned_entry)

        # Append unmatched semantic blocks
        for idx, sem_entry in enumerate(semantic_index):
            if idx not in used_semantic:
                sem_obj = sem_entry["obj"]
                result.append({
                    "spatial_block": None,  # No spatial anchor
                    "words": [],
                    "semantic_type": sem_obj.type,
                    "markdown_content": sem_obj.content
                })

        return result

    def _sort_by_reading_order(self, entries: list[dict]) -> list[dict]:
        """
        Sort blocks by reading order: top-to-bottom, then left-to-right.

        Uses the top-left corner (y0, x0) of each block's bbox.
        Blocks without spatial anchor go to the end.
        """
        def sort_key(entry):
            block = entry.get("spatial_block")
            if block is None:
                return (float('inf'), float('inf'))
            bbox = block.bbox
            if all(v == 0 for v in bbox):
                return (float('inf'), float('inf'))
            return (bbox[1], bbox[0])

        entries.sort(key=sort_key)
        return entries