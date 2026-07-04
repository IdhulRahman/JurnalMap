"""
PyMuPDF Parser - Extracts spatial objects from PDF.

This parser produces TWO types of spatial data:
1. Word-level objects: individual words with precise bounding boxes
2. Block-level objects: text and image blocks with bounding boxes

The parser does NOT know about pymupdf4llm or any other parser.
It only extracts what PyMuPDF sees: the raw spatial layout of the document.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional
from ..exceptions import PDFParseError


@dataclass
class RawWord:
    """Raw word extracted by PyMuPDF."""
    page: int
    text: str
    bbox: list[float]  # [x0, y0, x1, y1]
    block_id: int
    line_id: int
    word_id: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RawSpatialBlock:
    """Raw spatial block extracted by PyMuPDF (text or image block with bbox)."""
    page: int
    type: str  # "text" or "image"
    bbox: list[float]
    content: str
    block_number: int
    width: float = 0.0
    height: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SpatialOutput:
    """
    Complete output from the PyMuPDF parser.

    Contains both word-level and block-level spatial data.
    """
    words: list[RawWord]
    blocks: list[RawSpatialBlock]
    page_dimensions: dict[int, tuple[float, float]]  # page_num -> (width, height)

    def to_dict(self) -> dict:
        return {
            "words": [w.to_dict() for w in self.words],
            "blocks": [b.to_dict() for b in self.blocks],
            "page_dimensions": {
                str(k): v for k, v in self.page_dimensions.items()
            }
        }


class PyMuPDFParser:
    """
    Parses PDF using PyMuPDF to extract spatial layout data.

    Output: Raw word objects and spatial block objects with bounding boxes.
    Neither knows about any other parser.
    """

    def __init__(self):
        pass

    def parse(self, pdf_path: str) -> SpatialOutput:
        """
        Parse a PDF and extract spatial objects.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            SpatialOutput containing words and blocks.

        Raises:
            PDFParseError: If parsing fails.
        """
        try:
            import pymupdf
        except ImportError:
            raise ImportError("pymupdf is required. Install with: pip install pymupdf")

        try:
            doc = pymupdf.open(pdf_path)
        except Exception as e:
            raise PDFParseError(f"Failed to open PDF: {e}")

        words: list[RawWord] = []
        blocks: list[RawSpatialBlock] = []
        page_dimensions: dict[int, tuple[float, float]] = {}

        for page_num in range(len(doc)):
            page = doc[page_num]
            page_width = page.rect.width
            page_height = page.rect.height
            page_dimensions[page_num + 1] = (page_width, page_height)

            # --- Word-level extraction ---
            # get_text("words") returns: (x0, y0, x1, y1, word, block_no, line_no, word_no)
            word_list = page.get_text("words")

            for w in word_list:
                x0, y0, x1, y1, word_text, block_no, line_no, word_no = w
                words.append(RawWord(
                    page=page_num + 1,
                    text=word_text,
                    bbox=[x0, y0, x1, y1],
                    block_id=block_no,
                    line_id=line_no,
                    word_id=word_no
                ))

            # --- Block-level extraction ---
            blocks_dict = page.get_text("dict")["blocks"]

            for block in blocks_dict:
                block_type = block.get("type", 0)  # 0=text, 1=image
                block_bbox = block.get("bbox", [0, 0, 0, 0])
                block_number = block.get("number", 0)

                if block_type == 0:  # Text block
                    text_content = ""
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text_content += span.get("text", "") + " "

                    text_content = text_content.strip()
                    if text_content:
                        blocks.append(RawSpatialBlock(
                            page=page_num + 1,
                            type="text",
                            bbox=list(block_bbox),
                            content=text_content,
                            block_number=block_number,
                            width=block_bbox[2] - block_bbox[0],
                            height=block_bbox[3] - block_bbox[1]
                        ))

                elif block_type == 1:  # Image block
                    blocks.append(RawSpatialBlock(
                        page=page_num + 1,
                        type="image",
                        bbox=list(block_bbox),
                        content="",
                        block_number=block_number,
                        width=block_bbox[2] - block_bbox[0],
                        height=block_bbox[3] - block_bbox[1]
                    ))

        doc.close()
        return SpatialOutput(words=words, blocks=blocks, page_dimensions=page_dimensions)