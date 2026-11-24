"""Wiring tracer bullet: a local .pdf READ routes through the PDF extractor."""

import pytest

from teddy_executor.core.domain.models.action_ports import ActionPorts
from teddy_executor.core.services.action_factory import ActionFactory
from tests.harness.setup.fake_pdf_extractor import FakePdfExtractor
from tests.harness.setup.pdf_fixture import build_minimal_pdf


@pytest.fixture
def pdf_read(  # noqa: PLR0913  # Six port mocks mirror the ActionPorts constructor.
    mock_shell,
    mock_fs,
    mock_user_interactor,
    mock_scraper,
    mock_searcher,
    mock_config,
):
    extractor = FakePdfExtractor("Quarterly Report body")
    ports = ActionPorts(
        shell_executor=mock_shell,
        file_system_manager=mock_fs,
        user_interactor=mock_user_interactor,
        web_scraper=mock_scraper,
        web_searcher=mock_searcher,
        config_service=mock_config,
        pdf_extractor=extractor,
    )
    return ActionFactory(ports), extractor


def test_local_pdf_read_returns_extracted_text(pdf_read, mock_fs):
    factory, extractor = pdf_read
    payload = build_minimal_pdf("Quarterly Report")
    mock_fs.read_file_bytes.return_value = payload

    action = factory.create_action(
        "READ", {"resource": "report.pdf", "path": "report.pdf"}
    )
    result = action.execute(path="report.pdf")

    assert result == "Quarterly Report body"
    assert extractor.calls == [(payload, "report.pdf")]


def test_non_pdf_local_read_is_unchanged(pdf_read, mock_fs):
    factory, extractor = pdf_read
    mock_fs.read_file.return_value = "print('hi')"

    action = factory.create_action(
        "READ", {"resource": "script.py", "path": "script.py"}
    )
    result = action.execute(path="script.py")

    assert result == "print('hi')"
    assert extractor.calls == []
