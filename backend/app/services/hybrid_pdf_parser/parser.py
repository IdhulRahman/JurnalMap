"""
HybridParser - Public API for the hybrid PDF parsing library.

This is the main entry point. It orchestrates the full pipeline:
1. Parse PDF with both PyMuPDF (spatial) and pymupdf4llm (semantic)
2. Normalize both outputs into unified DocumentObjects
3. Align spatial and semantic data
4. Build the final Unified Document Representation (UDR)

Usage:
    from hybrid_pdf_parser import HybridParser

    parser = HybridParser()
    doc = parser.parse("paper.pdf")
    doc.to_dict()
    doc.to_json()
    doc.save_json("paper.json")
"""
from __future__ import annotations
import os
from typing import Optional, Callable

from .models import Document, Page, Block, Word, Metadata
from .parsers import PyMuPDFParser, PyMuPDF4LLMParser
from .normalization import Normalizer, DocumentObject
from .alignment import Aligner
from .exceptions import PDFNotFoundError, PDFParseError


class HybridParser:
    """
    Hybrid PDF Parser that integrates spatial and semantic representations.

    The parser runs two independent parsers internally:
    - PyMuPDF: extracts word-level spatial data with bounding boxes
    - pymupdf4llm: extracts block-level semantic data (tables, headings, etc.)

    Their outputs are normalized, aligned, and merged into a single
    Unified Document Representation (UDR).
    """

    def __init__(
        self,
        similarity_fn: Optional[Callable[[str, str], float]] = None,
        similarity_threshold: float = 0.2,
        bbox_tolerance: float = 2.0
    ):
        """
        Initialize the hybrid parser.

        Args:
            similarity_fn: Custom similarity function for semantic alignment.
                Default: Jaccard similarity.
            similarity_threshold: Minimum score to consider a semantic match (0.0-1.0).
            bbox_tolerance: Pixel tolerance for bounding box containment.
        """
        self._pymupdf_parser = PyMuPDFParser()
        self._llm_parser = PyMuPDF4LLMParser()
        self._normalizer = Normalizer()
        self._aligner = Aligner(
            similarity_fn=similarity_fn,
            similarity_threshold=similarity_threshold,
            bbox_tolerance=bbox_tolerance
        )

    def parse(self, pdf_path: str) -> Document:
        """
        Parse a PDF file and return a Unified Document Representation.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            Document: Unified Document Representation (UDR).

        Raises:
            PDFNotFoundError: If the file does not exist.
            PDFParseError: If parsing fails.
        """
        if not os.path.exists(pdf_path):
            raise PDFNotFoundError(f"PDF file not found: {pdf_path}")

        if not pdf_path.lower().endswith(".pdf"):
            raise PDFParseError(f"File must be a PDF: {pdf_path}")

        # --- Stage 1: Dual Parsing ---
        spatial_output = self._pymupdf_parser.parse(pdf_path)
        semantic_output = self._llm_parser.parse(pdf_path)

        # --- Stage 2: Normalization ---
        normalized = self._normalizer.normalize_all(
            words=spatial_output.words,
            spatial_blocks=spatial_output.blocks,
            semantic_blocks=semantic_output.blocks
        )

        # --- Stage 3: Alignment ---
        aligned = self._aligner.align(normalized, page_dimensions=spatial_output.page_dimensions)

        # --- Stage 4: Build UDR ---
        doc = self._build_document(
            aligned=aligned,
            source_file=os.path.basename(pdf_path),
            total_words=len(spatial_output.words),
            total_spatial_blocks=len(spatial_output.blocks),
            total_semantic_blocks=len(semantic_output.blocks)
        )

        return doc

    def _build_document(
        self,
        aligned: list[dict],
        source_file: str,
        total_words: int,
        total_spatial_blocks: int,
        total_semantic_blocks: int
    ) -> Document:
        """
        Build the final Document from aligned data.

        Args:
            aligned: Output from Aligner.align().
            source_file: Original PDF filename.
            total_words: Total word count.
            total_spatial_blocks: Total spatial block count.
            total_semantic_blocks: Total semantic block count.

        Returns:
            Document: The final Unified Document Representation.
        """
        total_blocks = sum(len(page_data["aligned"]) for page_data in aligned)

        metadata = Metadata(
            source_file=source_file,
            total_pages=len(aligned),
            total_words=total_words,
            total_blocks=total_blocks,
            parser_version="1.0.0",
            pipeline="hybrid_pdf_parser"
        )

        doc = Document(metadata=metadata)

        for page_data in aligned:
            page_num = page_data["page"]
            width = page_data.get("width", 0.0)
            height = page_data.get("height", 0.0)

            page = Page(
                page_number=page_num,
                width=width,
                height=height
            )

            for idx, entry in enumerate(page_data["aligned"]):
                spatial_block: Optional[DocumentObject] = entry.get("spatial_block")
                matching_words: list[DocumentObject] = entry.get("words", [])
                semantic_type: Optional[str] = entry.get("semantic_type")
                markdown_content: Optional[str] = entry.get("markdown_content")

                # Determine final type: semantic > spatial > default
                final_type = semantic_type or "paragraph"

                # Get bbox from spatial block, or zero if no spatial anchor
                if spatial_block:
                    bbox = spatial_block.bbox
                else:
                    bbox = [0.0, 0.0, 0.0, 0.0]

                # Generate block_id
                block_id = f"p{page_num:03d}b{idx:03d}"

                # Build markdown: semantic content > spatial content > word reconstruction
                if markdown_content:
                    markdown = markdown_content
                elif spatial_block and spatial_block.content:
                    markdown = spatial_block.content
                else:
                    markdown = " ".join(w.text for w in matching_words)

                # Build Word objects with order
                words = [
                    Word(text=w.text, bbox=w.bbox, order=order)
                    for order, w in enumerate(matching_words)
                ]

                # Handle image path
                image_path = None
                if final_type == "image":
                    if spatial_block and spatial_block.metadata:
                        image_path = spatial_block.metadata.get("image_path")
                    if not image_path and entry.get("markdown_content"):
                        # Try to extract from semantic metadata
                        pass

                block = Block(
                    block_id=block_id,
                    type=final_type,
                    bbox=bbox,
                    markdown=markdown,
                    words=words,
                    image_path=image_path
                )

                page.blocks.append(block)

            doc.pages.append(page)

        return doc