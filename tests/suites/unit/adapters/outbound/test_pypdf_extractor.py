"""Contract tests for the real pypdf-backed IPdfExtractor adapter."""

import pytest

from teddy_executor.core.domain.models.exceptions import PdfExtractionError
from teddy_executor.core.ports.outbound.pdf_extractor import IPdfExtractor
from tests.harness.setup.pdf_fixture import build_encrypted_pdf, build_minimal_pdf


@pytest.fixture
def extractor():
    from teddy_executor.adapters.outbound.pypdf_extractor import PypdfExtractor

    return PypdfExtractor()


def test_pypdf_extractor_satisfies_the_port(extractor):
    assert isinstance(extractor, IPdfExtractor)


def test_extracts_the_text_layer_from_a_valid_pdf(extractor):
    payload = build_minimal_pdf("Hello PDF")

    assert extractor.extract_text(payload, "doc.pdf") == "Hello PDF"


def test_rejects_a_pdf_named_payload_without_the_magic_bytes(extractor):
    with pytest.raises(PdfExtractionError) as exc_info:
        extractor.extract_text(b"not a pdf at all", "report.pdf")

    assert exc_info.value.source == "report.pdf"
    assert "%PDF" in str(exc_info.value)


def test_reports_a_corrupt_payload_as_a_pdf_extraction_error(extractor):
    with pytest.raises(PdfExtractionError) as exc_info:
        extractor.extract_text(b"%PDF-1.4\ngarbage", "broken.pdf")

    assert exc_info.value.source == "broken.pdf"


def test_reports_an_encrypted_payload_as_a_pdf_extraction_error(extractor):
    with pytest.raises(PdfExtractionError) as exc_info:
        extractor.extract_text(build_encrypted_pdf(), "secret.pdf")

    assert exc_info.value.source == "secret.pdf"


def test_reports_a_pdf_without_a_text_layer(extractor):
    with pytest.raises(PdfExtractionError) as exc_info:
        extractor.extract_text(build_minimal_pdf(""), "scan.pdf")

    assert exc_info.value.source == "scan.pdf"
    assert "text layer" in str(exc_info.value)


def test_pypdf_is_imported_lazily_through_a_private_getter():
    import teddy_executor.adapters.outbound.pypdf_extractor as module

    assert not hasattr(module, "pypdf")
    assert callable(getattr(module.PypdfExtractor, "_get_pypdf", None))
