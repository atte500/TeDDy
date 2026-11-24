from teddy_executor.core.domain.models.exceptions import (
    PdfExtractionError,
    TeddyError,
)


def test_teddy_error_is_the_project_root_exception():
    assert issubclass(TeddyError, Exception)


def test_pdf_extraction_error_inherits_from_teddy_error():
    assert issubclass(PdfExtractionError, TeddyError)


def test_pdf_extraction_error_carries_message_and_source():
    error = PdfExtractionError("no text layer", source="scan.pdf")

    assert str(error) == "no text layer"
    assert error.source == "scan.pdf"
