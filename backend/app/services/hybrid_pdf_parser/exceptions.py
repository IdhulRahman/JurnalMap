"""
Custom exceptions for the hybrid PDF parser library.
"""


class HybridParserError(Exception):
    """Base exception for all hybrid parser errors."""
    pass


class PDFNotFoundError(HybridParserError):
    """Raised when the specified PDF file does not exist."""
    pass


class PDFParseError(HybridParserError):
    """Raised when a parser fails to process the PDF."""
    pass


class AlignmentError(HybridParserError):
    """Raised when the alignment engine encounters an error."""
    pass


class NormalizationError(HybridParserError):
    """Raised when normalization fails."""
    pass