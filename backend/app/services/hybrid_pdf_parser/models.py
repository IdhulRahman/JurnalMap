"""
Domain models for the Unified Document Representation (UDR).

These classes represent the final output of the hybrid PDF parser.
They support conversion to dict, JSON, YAML, and Markdown.

Two markdown modes are available:
- to_markdown() / save_markdown()  → Clean presentation output
- preview() / save_preview()       → Verbose debug output with all metadata
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Metadata:
    """Document metadata."""
    source_file: str = ""
    total_pages: int = 0
    total_words: int = 0
    total_blocks: int = 0
    parser_version: str = "1.0.0"
    pipeline: str = "hybrid_pdf_parser"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Word:
    """A single word with its spatial position."""
    text: str
    bbox: list[float]  # [x0, y0, x1, y1]
    order: int = 0    # Word order within the block

    def to_dict(self) -> dict:
        return asdict(self)

    def _bbox_str(self) -> str:
        """Format bbox as compact string for debug comments."""
        b = self.bbox
        return f"[{b[0]:.1f},{b[1]:.1f},{b[2]:.1f},{b[3]:.1f}]"


@dataclass
class Block:
    """A block within a page (paragraph, table, image, etc.)."""
    block_id: str
    type: str           # 'paragraph', 'table', 'image', 'heading', 'list', 'code'
    bbox: list[float]   # [x0, y0, x1, y1] from PyMuPDF spatial data
    markdown: str = ""  # Markdown content from pymupdf4llm semantic data
    words: list[Word] = field(default_factory=list)
    image_path: Optional[str] = None
    metadata: Optional[dict] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["words"] = [w.to_dict() for w in self.words]
        return d

    def _bbox_str(self) -> str:
        """Format bbox as compact string for debug comments."""
        b = self.bbox
        return f"[{b[0]:.1f},{b[1]:.1f},{b[2]:.1f},{b[3]:.1f}]"

    def _to_markdown(self, preview: bool = False) -> str:
        """
        Render this block as markdown text.

        Args:
            preview: If True, include verbose debug comments.
                     If False, clean presentation output (no comments).

        Markdown is built from the Unified Document Representation (UDR),
        NOT by re-parsing the PDF. This ensures single-source-of-truth.
        """
        lines = []

        if preview:
            # Verbose debug comments
            lines.append(f"<!-- block_id: {self.block_id} -->")
            lines.append(f"<!-- type: {self.type} -->")
            if any(v != 0 for v in self.bbox):
                lines.append(f"<!-- bbox: {self._bbox_str()} -->")
            if self.words:
                lines.append(f"<!-- words: {len(self.words)} -->")
            if self.image_path:
                lines.append(f"<!-- image_path: {self.image_path} -->")
            if self.metadata:
                lines.append(f"<!-- metadata: {json.dumps(self.metadata)} -->")
        else:
            # Clean: only block_id and bbox for basic traceability
            lines.append(f"<!-- block_id: {self.block_id} -->")
            if any(v != 0 for v in self.bbox):
                lines.append(f"<!-- bbox: {self._bbox_str()} -->")

        type_map = {
            "heading": self._render_heading,
            "table": self._render_table,
            "image": self._render_image,
            "code": self._render_code,
            "list": self._render_list,
            "paragraph": self._render_paragraph,
        }

        renderer = type_map.get(self.type, self._render_paragraph)
        content = renderer()
        if content:
            lines.append(content)

        lines.append("")  # trailing blank line
        return "\n".join(lines)

    def _render_heading(self) -> str:
        """Render heading block."""
        text = self.markdown.strip().lstrip("#").strip()
        level = 1
        if self.metadata and "level" in self.metadata:
            level = self.metadata["level"]
        level = max(1, min(6, level))
        return f"{'#' * level} {text}"

    def _render_table(self) -> str:
        """Render table block."""
        return self.markdown.strip()

    def _render_image(self) -> str:
        """Render image block."""
        alt = self.markdown.strip() or "Figure"
        path = self.image_path or ""
        return f"![{alt}]({path})" if path else f"*Image: {alt}*"

    def _render_code(self) -> str:
        """Render code block."""
        lang = ""
        if self.metadata and "language" in self.metadata:
            lang = self.metadata["language"]
        return f"```{lang}\n{self.markdown.strip()}\n```"

    def _render_list(self) -> str:
        """Render list block."""
        items = self.markdown.strip().split("\n")
        rendered = []
        for item in items:
            stripped = item.strip()
            if stripped:
                clean = stripped.lstrip("- *").strip()
                rendered.append(f"- {clean}")
        return "\n".join(rendered)

    def _render_paragraph(self) -> str:
        """Render paragraph block."""
        return self.markdown.strip()


@dataclass
class Page:
    """A single page in the document."""
    page_number: int
    width: float = 0.0
    height: float = 0.0
    blocks: list[Block] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["blocks"] = [b.to_dict() for b in self.blocks]
        return d

    def _to_markdown(self, preview: bool = False) -> str:
        """Render this page as markdown text."""
        lines = []
        lines.append(f"<!-- page: {self.page_number} -->")
        if preview and self.width > 0 and self.height > 0:
            lines.append(f"<!-- page_dimensions: {self.width:.1f} x {self.height:.1f} -->")
        for block in self.blocks:
            lines.append(block._to_markdown(preview=preview))
        return "\n".join(lines)


@dataclass
class Document:
    """
    Unified Document Representation (UDR).

    The final output of the hybrid parser. Contains all extracted
    information in a unified, storage-independent format.
    Supports multiple output representations:
    - dict() → Python dictionary
    - to_json() → JSON string
    - to_markdown() → Clean Markdown string (presentation mode)
    - preview() → Verbose Markdown string (debug mode)
    - to_yaml() → YAML string (optional, requires PyYAML)
    """
    metadata: Metadata = field(default_factory=Metadata)
    pages: list[Page] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to Python dictionary."""
        return {
            "metadata": self.metadata.to_dict(),
            "pages": [p.to_dict() for p in self.pages]
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def to_markdown(self) -> str:
        """
        Convert to clean Markdown string (presentation mode).

        The markdown is built from the Unified Document Representation (UDR),
        NOT by re-parsing the PDF. This guarantees:
        - Single source of truth: JSON and Markdown represent the same data.
        - No duplicate parsing logic.
        - No re-calling parsers during export.

        For debugging with full metadata, use preview() instead.
        """
        return self._render_markdown(preview=False)

    def preview(self) -> str:
        """
        Convert to verbose Markdown string (debug mode).

        Includes full debug metadata as HTML comments:
        - page number and dimensions
        - block_id, type, bbox
        - word count per block
        - image paths
        - raw metadata dict

        Use this to verify alignment results during development.
        For clean output, use to_markdown() instead.
        """
        return self._render_markdown(preview=True)

    def _render_markdown(self, preview: bool = False) -> str:
        """Internal: render markdown in either presentation or debug mode."""
        lines = []
        lines.append(f"<!-- {self.metadata.pipeline} v{self.metadata.parser_version} -->")
        lines.append(f"<!-- source: {self.metadata.source_file} -->")
        lines.append(f"<!-- pages: {self.metadata.total_pages}, words: {self.metadata.total_words}, blocks: {self.metadata.total_blocks} -->")

        if preview:
            lines.append("<!-- ======================================== -->")
            lines.append("<!-- PREVIEW MODE: Full debug metadata below -->")
            lines.append("<!-- ======================================== -->")

        lines.append("")
        lines.append("# Document")
        lines.append("")

        for page in self.pages:
            page_md = page._to_markdown(preview=preview)
            lines.append(page_md)

        return "\n".join(lines)

    def to_yaml(self) -> str:
        """Convert to YAML string (requires PyYAML)."""
        try:
            import yaml
            return yaml.dump(self.to_dict(), default_flow_style=False, allow_unicode=True)
        except ImportError:
            raise ImportError(
                "PyYAML is required for YAML export. "
                "Install it with: pip install pyyaml"
            )

    def save_json(self, filepath: str, indent: int = 2) -> str:
        """Save to a JSON file."""
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=indent, ensure_ascii=False)
        return filepath

    def save_markdown(self, filepath: str) -> str:
        """Save clean Markdown to a file (presentation mode)."""
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        content = self.to_markdown()
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    def save_preview(self, filepath: str) -> str:
        """Save verbose debug Markdown to a file (debug mode)."""
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        content = self.preview()
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    def save_yaml(self, filepath: str) -> str:
        """Save to a YAML file (requires PyYAML)."""
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        content = self.to_yaml()
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath