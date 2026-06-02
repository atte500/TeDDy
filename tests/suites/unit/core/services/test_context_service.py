import pytest

from teddy_executor.core.domain.models import ProjectContext
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.web_scraper import WebScraper as IWebScraper
from teddy_executor.core.services.context_service import ContextService
from tests.harness.setup.mocking import register_mock


@pytest.fixture
def service(
    container, mock_fs, mock_tree_gen, mock_inspector, mock_llm_client
) -> IGetContextUseCase:
    """Provides a ContextService instance resolved from the container."""
    # Ensure dependencies are bound to the mocks for the service
    container.register(ILlmClient, instance=mock_llm_client)
    register_mock(container, IWebScraper)
    container.register(IGetContextUseCase, ContextService)
    return container.resolve(IGetContextUseCase)


def test_get_context_orchestrates_and_returns_correct_dto(
    service: IGetContextUseCase,
    mock_fs,
    mock_tree_gen,
    mock_inspector,
):
    """
    Scenario: Standardized Output Format (Service Level)
    Tests that get_context calls all its dependencies correctly and assembles
    the ProjectContext DTO with correctly formatted strings.
    """
    # Arrange
    # Simulate existing init.context file
    mock_fs.path_exists.return_value = True

    # Mock data from dependencies
    mock_sys_info = {
        "os_name": "test_os",
        "shell": "/bin/test",
        "cwd": "/test/dir",
        "os_version": "1.0",
        "current_date": "2026-03-26",
        "current_time": "16:50:00",
    }
    mock_git_status = " M file.py\n?? new.txt"
    mock_repo_tree = "dir/\n  file.txt"
    mock_vault_paths = ["file1.txt", "file2.py"]
    mock_file_contents = {"file1.txt": "content1", "file2.py": "print('hello')"}

    mock_inspector.get_environment_info.return_value = mock_sys_info
    mock_inspector.get_git_status.return_value = mock_git_status
    mock_tree_gen.generate_tree.return_value = mock_repo_tree
    mock_fs.get_context_paths.return_value = mock_vault_paths
    mock_fs.read_files_in_vault.return_value = mock_file_contents

    # Act
    result = service.get_context()

    # Assert
    # Check that dependencies were called correctly
    mock_inspector.get_environment_info.assert_called_once()
    mock_inspector.get_git_status.assert_called_once()
    mock_tree_gen.generate_tree.assert_called_once()
    mock_fs.get_context_paths.assert_called_once()
    mock_fs.read_files_in_vault.assert_called_once_with(mock_vault_paths)

    # Check the type of the returned DTO
    assert isinstance(result, ProjectContext)

    # Check header content (now part of the unified markdown)
    assert "# Project Context" in result.header
    assert "## 1. System Information" in result.header
    assert "- **CWD:** /test/dir" in result.header
    assert "- **OS:** test_os" in result.header
    assert "- **Current Date:** 2026-03-26" in result.header
    assert "- **Current Time:** 16:50:00" in result.header

    # Check git status section
    assert result.git_status == mock_git_status
    assert "## 2. Git Status" in result.content
    assert mock_git_status in result.content

    # Check main content sections
    assert "## 3. Project Structure" in result.content
    assert mock_repo_tree in result.content
    assert "## 4. Context Summary" not in result.content
    assert "## 4. Resource Contents" in result.content

    # Check resource formatting
    assert "[file1.txt](/file1.txt)" in result.content
    assert "```text\ncontent1\n```" in result.content
    assert "[file2.py](/file2.py)" in result.content
    assert "```python\nprint('hello')\n```" in result.content


def test_get_context_distinguishes_between_manifests_and_targets(
    service: IGetContextUseCase,
    mock_fs,
    mock_tree_gen,
    mock_inspector,
):
    """
    Tests that ContextService resolves .context files as manifests but treats
    other files (like .py or .md) as direct targets.
    """
    # Arrange
    files = ["session.context", "README.md"]
    mock_fs.resolve_paths_from_files.return_value = ["file_a.py"]
    mock_file_contents = {"file_a.py": "content_a", "README.md": "content_readme"}

    mock_inspector.get_environment_info.return_value = {}
    mock_inspector.get_git_status.return_value = None
    mock_tree_gen.generate_tree.return_value = ""
    mock_fs.read_files_in_vault.return_value = mock_file_contents

    # Act
    service.get_context(context_files={"Default": files})

    # Assert
    # session.context should be resolved once
    mock_fs.resolve_paths_from_files.assert_called_once_with(["session.context"])
    # README.md should be treated as target directly. Resulting set: {file_a.py, README.md}
    # Note: Order depends on input order
    mock_fs.read_files_in_vault.assert_called_once_with(["file_a.py", "README.md"])


def test_get_context_uses_dynamic_fences_for_safe_encapsulation(
    service, mock_fs, mock_tree_gen, mock_inspector
):
    """Tests that resource contents are wrapped in dynamic fences to prevent collisions."""
    # Arrange
    content_with_backticks = "Code with fence: ```python\nprint('hi')\n```"
    mock_fs.get_context_paths.return_value = ["tricky.md"]
    mock_fs.read_files_in_vault.return_value = {"tricky.md": content_with_backticks}
    mock_inspector.get_environment_info.return_value = {}
    mock_inspector.get_git_status.return_value = None
    mock_tree_gen.generate_tree.return_value = ""

    # Act
    result = service.get_context()

    # Assert
    # Should use 4 backticks because content has 3
    assert (
        "````markdown\nCode with fence: ```python\nprint('hi')\n```\n````"
        in result.content
    )


def test_get_context_always_includes_git_status_even_if_empty(
    service, mock_fs, mock_tree_gen, mock_inspector
):
    """Tests that the Git Status section is present even if the status is an empty string."""
    # Arrange
    mock_inspector.get_git_status.return_value = ""  # Clean repo
    mock_inspector.get_environment_info.return_value = {}
    mock_tree_gen.generate_tree.return_value = ""
    mock_fs.get_context_paths.return_value = []

    # Act
    result = service.get_context()

    # Assert
    assert "## 2. Git Status" in result.content
    assert "nothing to commit, working tree clean" in result.content


def test_get_context_populates_context_items_with_metadata(
    service: IGetContextUseCase,
    mock_fs,
    mock_tree_gen,
    mock_inspector,
    mock_llm_client,
):
    """
    Tests that get_context populates the 'items' list with ContextItem DTOs
    containing token counts and git status.
    """
    # Arrange
    mock_file_contents = {
        "src/core.py": "def main(): pass",
        "README.md": "# TeDDy",
        "new_file.txt": "hello",
    }
    # Mock Git Status: core.py is modified, README is unmodified, new_file is untracked
    mock_git_status = " M src/core.py\n?? new_file.txt"

    mock_inspector.get_environment_info.return_value = {}
    mock_inspector.get_git_status.return_value = mock_git_status
    mock_tree_gen.generate_tree.return_value = ""
    mock_fs.resolve_paths_from_files.side_effect = lambda files: files
    mock_fs.read_files_in_vault.return_value = mock_file_contents

    # Mock token counting
    def mock_token_counter(text, model=None):
        return len(text.split()) * 10  # Dummy token logic

    mock_llm_client.get_text_token_count.side_effect = mock_token_counter

    # Act
    result = service.get_context(
        context_files={
            "Session": ["src/core.py", "README.md"],
            "Turn": ["new_file.txt"],
        }
    )

    # Assert
    assert len(result.items) == 3

    # Check src/core.py (Modified, Session scope)
    core_item = next(i for i in result.items if i.path == "src/core.py")
    assert core_item.git_status == "M"
    assert core_item.scope == "Session"
    assert core_item.token_count == 30  # "def main(): pass" -> 3 words * 10
    assert core_item.selected is True

    # Check README.md (Unmodified, Session scope)
    readme_item = next(i for i in result.items if i.path == "README.md")
    assert readme_item.git_status == ""
    assert readme_item.scope == "Session"
    assert readme_item.token_count == 20  # "# TeDDy" -> 2 words * 10

    # Check new_file.txt (Untracked -> 'U', Turn scope)
    new_item = next(i for i in result.items if i.path == "new_file.txt")
    assert new_item.git_status == "U"  # Guideline: ?? -> U
    assert new_item.scope == "Turn"
    assert new_item.token_count == 10


def test_get_context_with_long_content_file_does_not_crash(
    service: IGetContextUseCase,
    mock_fs,
    mock_llm_client,
    mock_inspector,
    mock_tree_gen,
):
    """
    REGRESSION: Ensure that passing a file with long content (e.g. a spec)
    via the context mapping does not trigger manifest resolution which would
    treat lines of content as file paths.
    """
    # Arrange
    long_content = "This is a very long line of text " * 100
    mock_inspector.get_environment_info.return_value = {}
    mock_inspector.get_git_status.return_value = None
    mock_tree_gen.generate_tree.return_value = ""
    mock_fs.read_files_in_vault.return_value = {"long_spec.md": long_content}
    mock_llm_client.get_text_token_count.return_value = 50

    # Act (Should not call resolve_paths_from_files, avoiding crash on real FS)
    result = service.get_context(context_files={"Spec": ["long_spec.md"]})

    # Assert
    assert len(result.items) == 1
    assert result.items[0].path == "long_spec.md"
    assert result.items[0].token_count == 50
    mock_fs.resolve_paths_from_files.assert_not_called()


def test_get_context_separates_and_formats_session_history(
    service: IGetContextUseCase,
    mock_fs,
    mock_tree_gen,
    mock_inspector,
):
    """
    Scenario 1: Formatting chronological session history for the context payload.
    Verifies that ContextService partitions session history files from workspace files,
    excluding session files from '## 4. Resource Contents' and formatting them in
    '## 5. Session History' at the end, sorted chronologically. Unrecognized session
    files (like meta.yaml) are completely omitted. If no session files exist,
    the section is omitted entirely.
    """
    # Arrange
    session_prefix = ".teddy/sessions/20260521_134944-test-session"
    mock_file_contents = {
        f"{session_prefix}/initial_request.md": "Implement user login",
        f"{session_prefix}/01/meta.yaml": "some_meta: data",  # unrecognized
        f"{session_prefix}/01/plan.md": "Plan for step 1",
        f"{session_prefix}/01/report.md": "Report for step 1",
        "src/main.py": "print('hello')",  # standard workspace file
    }

    mock_inspector.get_environment_info.return_value = {}
    mock_inspector.get_git_status.return_value = ""
    mock_tree_gen.generate_tree.return_value = "src/main.py"
    mock_fs.resolve_paths_from_files.side_effect = lambda files: files
    mock_fs.read_files_in_vault.return_value = mock_file_contents

    # Act
    # Pass both session files and normal files
    result = service.get_context(
        context_files={
            "Session": [
                f"{session_prefix}/initial_request.md",
                f"{session_prefix}/01/meta.yaml",
            ],
            "Turn": [
                f"{session_prefix}/01/plan.md",
                f"{session_prefix}/01/report.md",
                "src/main.py",
            ],
        }
    )

    # Assert
    # 1. Standard workspace file MUST be in '## 4. Resource Contents'
    assert "## 4. Resource Contents" in result.content
    assert "### [src/main.py]" in result.content
    assert "print('hello')" in result.content

    # 2. Session files MUST NOT be in '## 4. Resource Contents'
    # We slice content to check within '## 4' block but before '## 5'
    assert "## 5. Session History" in result.content
    resource_contents_block = result.content.split("## 4. Resource Contents")[1].split(
        "## 5. Session History"
    )[0]
    assert "initial_request.md" not in resource_contents_block
    assert "plan.md" not in resource_contents_block
    assert "report.md" not in resource_contents_block
    assert (
        "meta.yaml" not in result.content
    )  # Unrecognized session file completely omitted

    # 3. '## 5. Session History' at the end in correct order with formatted headers and no raw directory paths
    history_block = result.content.split("## 5. Session History")[1]
    assert "### Initial Request" in history_block
    assert "Implement user login" in history_block
    assert "### Turn 1: Plan" in history_block
    assert "Plan for step 1" in history_block
    assert "### Turn 1: Execution Report" in history_block
    assert "Report for step 1" in history_block

    # Assert correct ordering
    idx_req = history_block.index("### Initial Request")
    idx_plan = history_block.index("### Turn 1: Plan")
    idx_report = history_block.index("### Turn 1: Execution Report")
    assert idx_req < idx_plan < idx_report

    # Ensure no raw directory paths exist under Session History
    assert ".teddy/sessions/" not in history_block


def test_get_context_omits_session_history_if_none_present(
    service: IGetContextUseCase,
    mock_fs,
    mock_tree_gen,
    mock_inspector,
):
    """
    Verifies that '## 5. Session History' is omitted entirely if there are no session files in the context.
    """
    # Arrange
    mock_inspector.get_environment_info.return_value = {}
    mock_inspector.get_git_status.return_value = ""
    mock_tree_gen.generate_tree.return_value = ""
    mock_fs.read_files_in_vault.return_value = {"src/main.py": "print('hello')"}

    # Act
    result = service.get_context(context_files={"Turn": ["src/main.py"]})

    # Assert
    assert "## 4. Resource Contents" in result.content
    assert "## 5. Session History" not in result.content


def test_get_context_deduplicates_overlapping_paths_prioritizing_non_turn_scope(
    service: IGetContextUseCase,
    mock_fs,
    mock_tree_gen,
    mock_inspector,
    mock_llm_client,
):
    """
    Scenario: Context Deduplication
    Tests that when a path appears in both 'Session' and 'Turn' scopes,
    only one ContextItem is returned, and it prefers the 'Session' scope.
    """
    # Arrange
    overlapping_path = "shared_file.txt"
    mock_file_contents = {overlapping_path: "content"}

    mock_inspector.get_environment_info.return_value = {}
    mock_inspector.get_git_status.return_value = None
    mock_tree_gen.generate_tree.return_value = ""
    mock_fs.resolve_paths_from_files.side_effect = lambda files: files
    mock_fs.read_files_in_vault.return_value = mock_file_contents
    mock_llm_client.get_text_token_count.return_value = 10

    # Act
    # overlapping_path is in BOTH scopes
    result = service.get_context(
        context_files={
            "Session": [overlapping_path],
            "Turn": [overlapping_path],
        }
    )

    # Assert
    # 1. Total items should be 1 (deduplicated)
    assert len(result.items) == 1

    # 2. Scope should be "Session" (priority)
    assert result.items[0].path == overlapping_path
    assert result.items[0].scope == "Session"
