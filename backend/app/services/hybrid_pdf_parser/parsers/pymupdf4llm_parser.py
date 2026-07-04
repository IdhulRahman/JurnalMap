"""
PyMuPDF4LLM Parser - Extracts semantic objects from PDF.

This parser produces block-level semantic data:
- Paragraphs
- Headings
- Tables (markdown format)
- Images
- Code blocks

The parser does NOT know about PyMuPDF or any other parser.
It only extracts what pymupdf4llm sees: the markdown-based semantic structure.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional
from ..exceptions import PDFParseError


@dataclass
class RawSemanticBlock:
    """Raw semantic block extracted by pymupdf4llm."""
    page: int
    type: str  # 'paragraph', 'heading', 'table', 'image', 'code', 'list'
    content: str
    metadata: Optional[dict] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SemanticOutput:
    """
    Complete output from the pymupdf4llm parser.
    """
    blocks: list[RawSemanticBlock]

    def to_dict(self) -> dict:
        return {
            "blocks": [b.to_dict() for b in self.blocks]
        }


class PyMuPDF4LLMParser:
    """
    Parses PDF using pymupdf4llm to extract semantic structure.

    Output: Raw semantic block objects with types (paragraph, table, heading, etc.)
    and markdown content. No bounding boxes - this parser only understands semantics.
    """

    def __init__(self):
        pass

    def parse(self, pdf_path: str) -> SemanticOutput:
        """
        Parse a PDF and extract semantic objects.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            SemanticOutput containing semantic blocks.

        Raises:
            PDFParseError: If parsing fails.
        """
        try:
            import pymupdf4llm
        except ImportError:
            raise ImportError(
                "pymupdf4llm is required. Install with: pip install pymupdf4llm"
            )

        try:
            md_text = pymupdf4llm.to_markdown(pdf_path, page_chunks=True)
        except Exception as e:
            raise PDFParseError(f"Failed to parse with pymupdf4llm: {e}")

        blocks: list[RawSemanticBlock] = []

        for chunk in md_text:
            page_num = chunk.get("metadata", {}).get("page") or chunk.get("metadata", {}).get("page_number") or 1
            page_content = chunk.get("text", "")

            parsed = self._parse_markdown_blocks(page_content, page_num)
            blocks.extend(parsed)
        return SemanticOutput(blocks=blocks)

    def _parse_markdown_blocks(
        self,
        md_content: str,
        page_num: int
    ) -> list[RawSemanticBlock]:
        """
        Parse markdown content into semantic blocks.

        Detects tables, headings, code blocks, images, lists, and paragraphs.
        """
        blocks = []
        lines = md_content.split("\n")
        current_paragraph: list[str] = []
        in_table = False
        table_lines: list[str] = []
        in_code_block = False
        code_lines: list[str] = []
        in_list = False
        list_lines: list[str] = []

        for line in lines:
            stripped = line.strip()

            # --- Code blocks ---
            if stripped.startswith("```"):
                if in_code_block:
                    code_content = "\n".join(code_lines)
                    blocks.append(RawSemanticBlock(
                        page=page_num,
                        type="code",
                        content=code_content,
                        metadata={"language": "unknown"}
                    ))
                    code_lines = []
                    in_code_block = False
                else:
                    in_code_block = True
                continue

            if in_code_block:
                code_lines.append(line)
                continue

            # --- Tables ---
            if stripped.startswith("|") and "|" in stripped:
                in_table = True
                table_lines.append(line)
                continue
            else:
                if in_table and table_lines:
                    table_content = "\n".join(table_lines)
                    blocks.append(RawSemanticBlock(
                        page=page_num,
                        type="table",
                        content=table_content,
                        metadata={"format": "markdown"}
                    ))
                    table_lines = []
                    in_table = False

            # --- Images ---
            if stripped.startswith("!["):
                alt_end = stripped.find("](")
                if alt_end != -1:
                    path_end = stripped.find(")", alt_end)
                    if path_end != -1:
                        alt_text = stripped[2:alt_end]
                        img_path = stripped[alt_end + 2:path_end]
                        blocks.append(RawSemanticBlock(
                            page=page_num,
                            type="image",
                            content=alt_text,
                            metadata={"image_path": img_path}
                        ))
                continue

            # --- Headings ---
            if stripped.startswith("#"):
                level = len(stripped) - len(stripped.lstrip("#"))
                heading_text = stripped.lstrip("#").strip()
                blocks.append(RawSemanticBlock(
                    page=page_num,
                    type="heading",
                    content=heading_text,
                    metadata={"level": level}
                ))
                continue

            # --- List items ---
            if stripped.startswith("- ") or stripped.startswith("* "):
                in_list = True
                list_lines.append(stripped)
                continue
            else:
                if in_list and list_lines:
                    list_content = "\n".join(list_lines)
                    blocks.append(RawSemanticBlock(
                        page=page_num,
                        type="list",
                        content=list_content
                    ))
                    list_lines = []
                    in_list = False

            # --- Regular text (paragraph) ---
            if stripped:
                current_paragraph.append(stripped)
            else:
                if current_paragraph:
                    para_text = " ".join(current_paragraph)
                    blocks.append(RawSemanticBlock(
                        page=page_num,
                        type="paragraph",
                        content=para_text
                    ))
                    current_paragraph = []

        # Flush remaining paragraph
        if current_paragraph:
            para_text = " ".join(current_paragraph)
            blocks.append(RawSemanticBlock(
                page=page_num,
                type="paragraph",
                content=para_text
            ))

        # Flush remaining table
        if in_table and table_lines:
            table_content = "\n".join(table_lines)
            blocks.append(RawSemanticBlock(
                page=page_num,
                type="table",
                content=table_content,
                metadata={"format": "markdown"}
            ))

        # Flush remaining list
        if in_list and list_lines:
            list_content = "\n".join(list_lines)
            blocks.append(RawSemanticBlock(
                page=page_num,
                type="list",
                content=list_content
            ))

        return blocks