"""ActionFactory adopts the core PDF helpers: detection and the read cap."""

import pytest

from teddy_executor.core.domain.models.action_ports import ActionPorts
from teddy_executor.core.services.action_factory import ActionFactory
from teddy_executor.core.utils.pdf import cap_extracted_text
from tests.harness.setup.fake_pdf_extractor import FakePdfExtractor


@pytest.fixture
def factory_for(  # noqa: PLR0913  # Six port mocks mirror the ActionPorts constructor.
    mock_shell,
    mock_fs,
    mock_user_interactor,
    mock_scraper,
    mock_searcher,
    mock_config,
):
    def build(extractor):
        return ActionFactory(
            ActionPorts(
                shell_executor=mock_shell,
                file_system_manager=mock_fs,
                user_interactor=mock_user_interactor,
                web_scraper=mock_scraper,
                web_searcher=mock_searcher,
                config_service=mock_config,
                pdf_extractor=extractor,
            )
        )

    return build


def test_query_string_pdf_source_routes_through_the_extractor(factory_for, mock_fs):
    extractor = FakePdfExtractor("Quarterly Report body")
    factory = factory_for(extractor)
    payload = b"%PDF-1.4\nbody"
    mock_fs.read_file_bytes.return_value = payload
    source = "report.pdf?token=abc"

    action = factory.create_action("READ", {"resource": source, "path": source})
    result = action.execute(path=source)

    assert result == "Quarterly Report body"
    assert extractor.calls == [(payload, source)]


def test_extracted_text_is_capped_at_read_max_lines(factory_for, mock_fs, mock_config):
    text = "\n".join(f"line{i}" for i in range(1, 6))
    factory = factory_for(FakePdfExtractor(text))
    mock_fs.read_file_bytes.return_value = b"%PDF-1.4\n"
    mock_config.get_setting.side_effect = lambda key, default=None: (
        3 if key == "read.max_lines" else default
    )

    action = factory.create_action(
        "READ", {"resource": "report.pdf", "path": "report.pdf"}
    )
    result = action.execute(path="report.pdf")

    assert result == cap_extracted_text(text, 3)


def test_extracted_text_is_verbatim_without_a_configured_cap(
    factory_for, mock_fs, mock_config
):
    text = "\n".join(f"line{i}" for i in range(1, 6))
    factory = factory_for(FakePdfExtractor(text))
    mock_fs.read_file_bytes.return_value = b"%PDF-1.4\n"
    mock_config.get_setting.side_effect = lambda key, default=None: default

    action = factory.create_action(
        "READ", {"resource": "report.pdf", "path": "report.pdf"}
    )
    result = action.execute(path="report.pdf")

    assert result == text


def test_source_without_a_pdf_extension_keeps_the_text_read_path(factory_for, mock_fs):
    extractor = FakePdfExtractor()
    factory = factory_for(extractor)
    mock_fs.read_file.return_value = "plain text"
    source = "download?id=5"

    action = factory.create_action("READ", {"resource": source, "path": source})
    result = action.execute(path=source)

    assert result == "plain text"
    assert extractor.calls == []


def test_pdf_read_ignores_a_lines_range(factory_for, mock_fs):
    extractor = FakePdfExtractor("Full text")
    factory = factory_for(extractor)
    mock_fs.read_file_bytes.return_value = b"%PDF-1.4\n"
    params = {"resource": "report.pdf", "path": "report.pdf", "lines": "2-5"}

    action = factory.create_action("READ", params)
    result = action.execute(path="report.pdf", lines="2-5")

    assert result == "Full text"
    assert extractor.calls == [(b"%PDF-1.4\n", "report.pdf")]
