"""
Normalization Layer - Converts raw parser outputs into unified DocumentObjects.

Each parser output is normalized independently. The normalizer does NOT know
about other parsers - it only transforms format.

Three types of objects are normalized:
1. RawWord (from PyMuPDF) → type="word"
2. RawSpatialBlock (from PyMuPDF) → type="spatial_block"
3. RawSemanticBlock (from pymupdf4llm) → type=original_type (paragraph, table, etc.)

All normalized objects share the same DocumentObject schema.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional
from .utils import generate_uuid, normalize_bbox, normalize_page


SEMANTIC_TYPE_MAP = {
    "paragraph": "paragraph",
    "heading": "heading",
    "table": "table",
    "image": "image",
    "code": "code",
    "list": "list",
    "text": "paragraph",  # PyMuPDF text blocks become paragraphs
}


@dataclass
class DocumentObject:
    """
    Normalized document object with unified schema.

    All parser outputs are converted to this form during normalization.
    """
    id: str = field(default_factory=generate_uuid)
    page: int = 0
    type: str = "paragraph"
    bbox: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    source: str = ""           # "PyMuPDF" or "pymupdf4llm"
    text: str = ""
    content: str = ""          # Full content (for blocks)
    block_id: Optional[int] = None
    line_id: Optional[int] = None
    word_id: Optional[int] = None
    metadata: Optional[dict] = None

    def to_dict(self) -> dict:
        return asdict(self)


class Normalizer:
    """
    Normalizes raw parser outputs into unified DocumentObjects.

    Each method handles one parser type independently.
    """

    def normalize_word(self, raw_word) -> DocumentObject:
        """Normalize a RawWord from PyMuPDF."""
        from .parsers.pymupdf_parser import RawWord
        return DocumentObject(
            id=generate_uuid(),
            page=normalize_page(raw_word.page),
            type="word",
            bbox=normalize_bbox(raw_word.bbox),
            source="PyMuPDF",
            text=raw_word.text,
            content=raw_word.text,
            block_id=raw_word.block_id,
            line_id=raw_word.line_id,
            word_id=raw_word.word_id
        )

    def normalize_spatial_block(self, raw_block) -> DocumentObject:
        """Normalize a RawSpatialBlock from PyMuPDF."""
        from .parsers.pymupdf_parser import RawSpatialBlock
        block_type = SEMANTIC_TYPE_MAP.get(raw_block.type, "paragraph")
        return DocumentObject(
            id=generate_uuid(),
            page=normalize_page(raw_block.page),
            type="spatial_block",
            bbox=normalize_bbox(raw_block.bbox),
            source="PyMuPDF",
            text=raw_block.content[:200] if raw_block.content else "",
            content=raw_block.content,
            metadata={
                "block_number": raw_block.block_number,
                "block_type": block_type,
                "width": raw_block.width,
                "height": raw_block.height
            }
        )

    def normalize_semantic_block(self, raw_block) -> DocumentObject:
        """Normalize a RawSemanticBlock from pymupdf4llm."""
        from .parsers.pymupdf4llm_parser import RawSemanticBlock
        obj_type = SEMANTIC_TYPE_MAP.get(raw_block.type, "paragraph")
        return DocumentObject(
            id=generate_uuid(),
            page=normalize_page(raw_block.page),
            type=obj_type,
            bbox=[0.0, 0.0, 0.0, 0.0],  # pymupdf4llm has no bbox
            source="pymupdf4llm",
            text=raw_block.content[:200] if raw_block.content else "",
            content=raw_block.content,
            metadata=raw_block.metadata
        )

    def normalize_all(
        self,
        words: list = None,
        spatial_blocks: list = None,
        semantic_blocks: list = None
    ) -> list[DocumentObject]:
        """
        Normalize all raw parser outputs into unified DocumentObjects.

        Args:
            words: List of RawWord from PyMuPDF parser.
            spatial_blocks: List of RawSpatialBlock from PyMuPDF parser.
            semantic_blocks: List of RawSemanticBlock from pymupdf4llm parser.

        Returns:
            list[DocumentObject]: All objects in unified schema.
        """
        result: list[DocumentObject] = []

        if words:
            for w in words:
                result.append(self.normalize_word(w))

        if spatial_blocks:
            for b in spatial_blocks:
                result.append(self.normalize_spatial_block(b))

        if semantic_blocks:
            for b in semantic_blocks:
                result.append(self.normalize_semantic_block(b))

        return result