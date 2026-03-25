import pytest

from teddy_executor.core.domain.models import ProjectContext
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.services.context_service import ContextService


@pytest.fixture
def service(container, mock_fs, mock_tree_gen, mock_inspector) -> IGetContextUseCase:
    """Provides a ContextService instance resolved from the container."""
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


def test_get_context_with_specific_files_uses_resolve_paths_from_files(
    service: IGetContextUseCase,
    mock_fs,
    mock_tree_gen,
    mock_inspector,
):
    """
    Tests that when specific context files are provided, ContextService
    calls resolve_paths_from_files instead of get_context_paths.
    """
    # Arrange
    specific_files = ["session.context", "turn.context"]
    mock_vault_paths = ["file_a.txt"]
    mock_file_contents = {"file_a.txt": "content_a"}

    mock_inspector.get_environment_info.return_value = {}
    mock_inspector.get_git_status.return_value = None
    mock_tree_gen.generate_tree.return_value = ""
    mock_fs.resolve_paths_from_files.return_value = mock_vault_paths
    mock_fs.read_files_in_vault.return_value = mock_file_contents

    # Act
    service.get_context(context_files={"Default": specific_files})

    # Assert
    mock_fs.resolve_paths_from_files.assert_called_once_with(specific_files)
    mock_fs.get_context_paths.assert_not_called()
    mock_fs.read_files_in_vault.assert_called_once_with(mock_vault_paths)


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
    assert "````markdown\nCode with fence: ```python\nprint('hi')\n```\n````" in result.content


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
