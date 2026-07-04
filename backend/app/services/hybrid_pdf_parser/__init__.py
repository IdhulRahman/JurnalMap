"""
hybrid_pdf_parser - A Hybrid PDF Parsing Library.

Integrates word-level spatial representation (PyMuPDF) with
block-level semantic representation (pymupdf4llm) through
normalization and alignment mechanisms.

Two output modes for human-readable content:
  - to_markdown() / save_markdown()  → Clean presentation output
  - preview() / save_preview()       → Verbose debug output with metadata

Usage:
    from hybrid_pdf_parser import HybridParser

    parser = HybridParser()
    doc = parser.parse("paper.pdf")

    # Export
    doc.to_dict()
    doc.to_json()
    doc.to_markdown()     # clean output
    doc.preview()         # debug output
    doc.save_json("paper.json")
    doc.save_markdown("paper.md")
    doc.save_preview("preview.md")
"""

from .parser import HybridParser
from .models import Document, Page, Block, Word, Metadata

__all__ = ["HybridParser", "Document", "Page", "Block", "Word", "Metadata"]
__version__ = "1.0.0"