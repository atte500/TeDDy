import pytest

from teddy_executor.core.domain.models.exceptions import PdfExtractionError
from teddy_executor.core.utils.pdf import (
    cap_extracted_text,
    has_pdf_magic,
    is_pdf_source,
    require_pdf_magic,
)
from teddy_executor.core.utils.string import get_truncation_hint, truncate_lines


@pytest.mark.parametrize(
    "source",
    [
        "report.pdf",
        "report.PDF",
        "Report.Pdf",
        "path/to/report.pdf",
        "https://example.com/file.pdf?token=abc",
        "https://example.com/file.pdf#page=2",
    ],
)
def test_is_pdf_source_recognises_pdf_paths_and_urls(source):
    assert is_pdf_source(source) is True


@pytest.mark.parametrize(
    "source",
    [
        "report.txt",
        "report.pdf.txt",
        "report",
        "https://example.com/download?id=5",
        "",
    ],
)
def test_is_pdf_source_rejects_non_pdf_sources(source):
    assert is_pdf_source(source) is False


def test_has_pdf_magic_accepts_the_pdf_header():
    assert has_pdf_magic(b"%PDF-1.7\n...") is True


@pytest.mark.parametrize("data", [b"", b"not a pdf", b"PK\x03\x04"])
def test_has_pdf_magic_rejects_non_pdf_payloads(data):
    assert has_pdf_magic(data) is False


def test_require_pdf_magic_accepts_a_pdf_payload():
    require_pdf_magic(b"%PDF-1.4\nbody", "doc.pdf")


def test_require_pdf_magic_names_the_source_on_mismatch():
    with pytest.raises(PdfExtractionError) as exc_info:
        require_pdf_magic(b"definitely not a pdf", source="report.pdf")

    assert exc_info.value.source == "report.pdf"
    assert "%PDF" in str(exc_info.value)


def test_cap_leaves_text_within_the_limit_untouched():
    text = "line1\nline2\nline3"

    assert cap_extracted_text(text, 3) == text


def test_cap_truncates_to_the_head_and_appends_the_read_hint():
    text = "\n".join(f"line{i}" for i in range(1, 6))

    result = cap_extracted_text(text, 3)

    hint = get_truncation_hint("read", 3, 5)
    assert result == "\n".join(["line1", "line2", "line3"]) + "\n" + hint


def test_cap_matches_the_shared_text_truncation_budget():
    text = "\n".join(f"row{i}" for i in range(10))

    assert cap_extracted_text(text, 4) == truncate_lines(
        text, 4, direction="head", action_type="read"
    )
