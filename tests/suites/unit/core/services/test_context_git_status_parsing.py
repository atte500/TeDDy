import pytest

from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.web_scraper import WebScraper as IWebScraper
from teddy_executor.core.services.context_service import ContextService
from tests.harness.setup.mocking import register_mock


@pytest.fixture
def service(
    container, mock_fs, mock_tree_gen, mock_inspector, mock_llm_client
) -> IGetContextUseCase:
    """Provides a ContextService wired to the shared port fakes."""
    container.register(ILlmClient, instance=mock_llm_client)
    register_mock(container, IWebScraper)
    container.register(IGetContextUseCase, ContextService)
    return container.resolve(IGetContextUseCase)


def _status_badges(result) -> dict[str, str]:
    return {item.path: item.git_status for item in result.items}


@pytest.mark.parametrize(
    ("git_status", "scoped_files", "expected_badges"),
    [
        ("## main...origin/main", [], {}),
        ("## feature/auth", [], {}),
        ("## HEAD (no branch)", [], {}),
        ("## No commits yet on main", [], {}),
        (
            "## main...origin/main\n M file.py\n?? new.txt",
            ["file.py", "new.txt"],
            {"file.py": "M", "new.txt": "U"},
        ),
        (
            "## main...origin/main\nR  old.py -> new.py",
            ["new.py"],
            {"new.py": "R"},
        ),
    ],
)
def test_get_context_maps_porcelain_status_to_item_badges(  # noqa: PLR0913
    service,
    mock_fs,
    mock_tree_gen,
    mock_inspector,
    git_status,
    scoped_files,
    expected_badges,
):
    """Scenario: each porcelain state resolves to the expected item badges."""
    mock_inspector.get_environment_info.return_value = {}
    mock_inspector.get_git_status.return_value = git_status
    mock_tree_gen.generate_tree.return_value = ""
    mock_fs.read_files_in_vault.return_value = {
        path: "content" for path in scoped_files
    }

    result = service.get_context(context_files={"Turn": scoped_files})

    assert _status_badges(result) == expected_badges


def test_get_context_renders_no_fence_without_git_status(
    service, mock_fs, mock_tree_gen, mock_inspector
):
    """Scenario: a non-git directory leaves the Git Status section unfenced."""
    mock_inspector.get_environment_info.return_value = {}
    mock_inspector.get_git_status.return_value = None
    mock_tree_gen.generate_tree.return_value = ""
    mock_fs.read_files_in_vault.return_value = {"file.py": "content"}

    result = service.get_context(context_files={"Turn": ["file.py"]})

    assert _status_badges(result) == {"file.py": ""}
    git_section = result.content.split("## Project Structure")[0]
    assert "## Git Status" in git_section
    assert "```" not in git_section
