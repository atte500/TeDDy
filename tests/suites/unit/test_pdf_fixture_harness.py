import io

import pytest
from pypdf import PdfReader

from tests.harness.setup.fake_pdf_extractor import FakePdfExtractor
from tests.harness.setup.pdf_fixture import DEFAULT_PDF_TEXT, build_minimal_pdf


@pytest.mark.parametrize("text", [DEFAULT_PDF_TEXT, "Quarterly Report", "Page One"])
def test_pypdf_extracts_the_built_text_layer(text):
    reader = PdfReader(io.BytesIO(build_minimal_pdf(text)))

    assert len(reader.pages) == 1
    assert text in reader.pages[0].extract_text()


def test_builder_output_carries_pdf_magic():
    assert build_minimal_pdf().startswith(b"%PDF-")


def test_fake_extractor_returns_configured_text_and_records_the_call():
    fake = FakePdfExtractor("body text")
    data = build_minimal_pdf()

    assert fake.extract_text(data, "doc.pdf") == "body text"
    assert fake.calls == [(data, "doc.pdf")]


def test_fake_extractor_fixture_registers_in_container(container, fake_pdf_extractor):
    from teddy_executor.core.ports.outbound import IPdfExtractor

    assert container.resolve(IPdfExtractor) is fake_pdf_extractor
