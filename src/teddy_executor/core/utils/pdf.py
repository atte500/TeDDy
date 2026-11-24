"""Pure helpers for recognising a PDF read and capping its extracted text."""

from teddy_executor.core.domain.models.exceptions import PdfExtractionError
from teddy_executor.core.utils.string import truncate_lines

PDF_MAGIC = b"%PDF-"


def is_pdf_source(source: str) -> bool:
    """Return True when the path or URL names a PDF document.

    Matching is case-insensitive and ignores any query string or fragment, so a
    signed URL such as ``file.pdf?token=...`` still counts.
    """
    without_query = source.split("?", 1)[0]
    without_fragment = without_query.split("#", 1)[0]
    return without_fragment.lower().endswith(".pdf")


def has_pdf_magic(data: bytes) -> bool:
    """Return True when the payload begins with the ``%PDF-`` magic bytes."""
    return data.startswith(PDF_MAGIC)


def require_pdf_magic(data: bytes, source: str) -> None:
    """Raise ``PdfExtractionError`` when a PDF-named payload lacks the magic bytes."""
    if has_pdf_magic(data):
        return
    raise PdfExtractionError(
        f"Payload for '{source}' does not start with the %PDF magic bytes",
        source=source,
    )


def cap_extracted_text(text: str, max_lines: int) -> str:
    """Apply the same head truncation a text file receives under ``read.max_lines``."""
    return truncate_lines(text, max_lines, direction="head", action_type="read")
