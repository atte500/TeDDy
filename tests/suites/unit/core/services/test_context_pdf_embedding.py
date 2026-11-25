"""A local PDF in the working set embeds its extracted text layer.

Context assembly embeds resources verbatim, so a PDF path registered by an
earlier READ must arrive as extracted text instead of being decoded as UTF-8.
"""

import pytest

from teddy_executor.core.services.context_service import ContextService
from teddy_executor.core.utils.pdf import cap_extracted_text
from tests.harness.setup.fake_pdf_extractor import FakePdfExtractor
from tests.harness.setup.pdf_fixture import build_minimal_pdf

PDF_PATH = "report.pdf"
UPPERCASE_PDF_PATH = "REPORT.PDF"
TEXT_PATH = "notes.md"
EXTRACTED_TEXT = "Extracted report body"
SESSION_ROOT = ".teddy/sessions/20260521_100000-report-review"


@pytest.fixture
def pdf_extractor() -> FakePdfExtractor:
    """A deterministic text layer, so assertions never depend on pypdf."""
    return FakePdfExtractor(EXTRACTED_TEXT)


@pytest.fixture
def service_factory(  # noqa: PLR0913 - mirrors the service's port set
    mock_fs, mock_tree_gen, mock_inspector, mock_llm_client, mock_scraper
):
    """Build the service with only the PDF-related handles varying per test."""

    def build(pdf_extractor=None, config_service=None) -> ContextService:
        return ContextService(
            file_system_manager=mock_fs,
            repo_tree_generator=mock_tree_gen,
            environment_inspector=mock_inspector,
            llm_client=mock_llm_client,
            web_scraper=mock_scraper,
            config_service=config_service,
            pdf_extractor=pdf_extractor,
        )

    return build


@pytest.fixture
def service(service_factory, pdf_extractor) -> ContextService:
    """The service under test, wired to the fake extractor."""
    return service_factory(pdf_extractor=pdf_extractor)


def arrange_incidental_ports(mock_fs, mock_tree_gen, mock_inspector, contents=None):
    """Stub the ports that only carry incidental payload furniture."""
    mock_inspector.get_environment_info.return_value = {}
    mock_inspector.get_git_status.return_value = None
    mock_tree_gen.generate_tree.return_value = ""
    mock_fs.is_dir.return_value = False
    mock_fs.resolve_paths_from_files.side_effect = lambda files: files
    mock_fs.read_files_in_vault.return_value = contents or {}


def test_a_pdf_only_scope_embeds_extracted_text_without_decoding(
    service, mock_fs, mock_tree_gen, mock_inspector, pdf_extractor
):
    """The vault reader never sees a PDF path, so no UTF-8 decode can happen."""
    arrange_incidental_ports(mock_fs, mock_tree_gen, mock_inspector)
    payload = build_minimal_pdf()
    mock_fs.read_file_bytes.return_value = payload

    result = service.get_context(
        context_files={"Turn": [PDF_PATH]}, include_tokens=False
    )

    assert EXTRACTED_TEXT in result.content
    assert "--- FILE NOT FOUND ---" not in result.content
    assert "Showing first" not in result.content
    mock_fs.read_files_in_vault.assert_called_once_with([])
    mock_fs.read_file_bytes.assert_called_once_with(PDF_PATH)
    assert pdf_extractor.calls == [(payload, PDF_PATH)]


def test_a_mixed_scope_reads_only_the_text_path_through_the_vault(
    service, mock_fs, mock_tree_gen, mock_inspector
):
    """A PDF never reaches the verbatim reader while text resources still do."""
    arrange_incidental_ports(
        mock_fs, mock_tree_gen, mock_inspector, {TEXT_PATH: "note body"}
    )
    mock_fs.read_file_bytes.return_value = build_minimal_pdf()

    result = service.get_context(
        context_files={"Turn": [PDF_PATH, TEXT_PATH]}, include_tokens=False
    )

    mock_fs.read_files_in_vault.assert_called_once_with([TEXT_PATH])
    assert "note body" in result.content
    assert EXTRACTED_TEXT in result.content


def test_an_uppercase_extension_is_treated_as_a_pdf(
    service, mock_fs, mock_tree_gen, mock_inspector
):
    """Extension matching is case-insensitive, so `.PDF` routes like `.pdf`."""
    arrange_incidental_ports(mock_fs, mock_tree_gen, mock_inspector)
    mock_fs.read_file_bytes.return_value = build_minimal_pdf()

    result = service.get_context(
        context_files={"Turn": [UPPERCASE_PDF_PATH]}, include_tokens=False
    )

    assert EXTRACTED_TEXT in result.content
    mock_fs.read_files_in_vault.assert_called_once_with([])


def test_a_missing_pdf_renders_the_not_found_marker(
    service, mock_fs, mock_tree_gen, mock_inspector
):
    """A vanished PDF keeps the marker contract instead of raising."""
    arrange_incidental_ports(mock_fs, mock_tree_gen, mock_inspector)
    mock_fs.read_file_bytes.side_effect = FileNotFoundError(PDF_PATH)

    result = service.get_context(
        context_files={"Turn": [PDF_PATH]}, include_tokens=False
    )

    assert "--- FILE NOT FOUND ---" in result.content


def test_extracted_text_is_head_truncated_at_read_max_lines(
    service_factory, mock_fs, mock_tree_gen, mock_inspector, mock_config
):
    """A PDF obeys the same budget and notice as a long text file."""
    arrange_incidental_ports(mock_fs, mock_tree_gen, mock_inspector)
    mock_fs.read_file_bytes.return_value = build_minimal_pdf()
    text = "\n".join(f"line {number}" for number in range(1, 11))
    mock_config.get_setting.side_effect = lambda key, default=None: (
        3 if key == "read.max_lines" else default
    )
    service = service_factory(
        pdf_extractor=FakePdfExtractor(text), config_service=mock_config
    )

    result = service.get_context(
        context_files={"Turn": [PDF_PATH]}, include_tokens=False
    )

    assert cap_extracted_text(text, 3) in result.content
    assert "line 10" not in result.content


def test_a_pdf_without_the_extractor_port_fails_the_contract(
    service_factory, mock_fs, mock_tree_gen, mock_inspector
):
    """A silently decoded PDF is exactly the defect, so the port is asserted."""
    arrange_incidental_ports(mock_fs, mock_tree_gen, mock_inspector)
    service = service_factory()

    with pytest.raises(AssertionError, match="pdf_extractor"):
        service.get_context(context_files={"Turn": [PDF_PATH]}, include_tokens=False)


def test_a_session_scoped_pdf_hoists_into_session_resources(
    service, mock_fs, mock_tree_gen, mock_inspector
):
    """Partitioning is a path decision, so it applies to every scope."""
    arrange_incidental_ports(mock_fs, mock_tree_gen, mock_inspector)
    mock_fs.read_file_bytes.return_value = build_minimal_pdf()

    result = service.get_context(
        context_files={"Session": [PDF_PATH]},
        include_tokens=False,
        session_root=SESSION_ROOT,
    )

    assert "## Session Resources" in result.content
    session_resources = result.content.split("## Session Resources")[1].split(
        "## Session History"
    )[0]
    assert EXTRACTED_TEXT in session_resources


def test_the_pdf_item_token_count_covers_the_extracted_text(
    service, mock_fs, mock_tree_gen, mock_inspector, mock_llm_client
):
    """Item metadata must describe the embedded body, not the raw bytes."""
    arrange_incidental_ports(mock_fs, mock_tree_gen, mock_inspector)
    mock_fs.read_file_bytes.return_value = build_minimal_pdf()
    mock_llm_client.get_text_token_count.side_effect = lambda text, model=None: len(
        text
    )

    result = service.get_context(context_files={"Turn": [PDF_PATH]})

    item = next(item for item in result.items if item.path == PDF_PATH)
    assert item.token_count == len(EXTRACTED_TEXT)
