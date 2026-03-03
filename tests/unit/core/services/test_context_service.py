import pytest
from unittest.mock import MagicMock

from teddy_executor.core.domain.models import ProjectContext
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.outbound.environment_inspector import (
    IEnvironmentInspector,
)
from teddy_executor.core.services.context_service import ContextService


@pytest.fixture
def mock_inspector(container):
    mock = MagicMock(spec=IEnvironmentInspector)
    container.register(IEnvironmentInspector, instance=mock)
    return mock


@pytest.fixture
def service(container, mock_fs, mock_tree_gen, mock_inspector) -> IGetContextUseCase:
    """Provides a ContextService instance resolved from the container."""
    container.register(IGetContextUseCase, ContextService)
    return container.resolve(IGetContextUseCase)


def test_get_context_creates_default_file_if_not_exists(
    service: IGetContextUseCase,
    mock_fs,
    mock_tree_gen,
    mock_inspector,
):
    """
    Scenario: Simplified Default Configuration (Service Level)
    Tests that get_context calls the file system manager to create the
    default context file if the permanent context file does not exist.
    """
    # Arrange
    mock_fs.path_exists.return_value = False

    # Mock return values for the rest of the function to avoid subsequent errors
    mock_tree_gen.generate_tree.return_value = ""
    mock_inspector.get_environment_info.return_value = {}
    mock_fs.get_context_paths.return_value = []
    mock_fs.read_files_in_vault.return_value = {}

    # Act
    service.get_context()

    # Assert
    mock_fs.path_exists.assert_called_once_with(".teddy/init.context")
    mock_fs.create_default_context_file.assert_called_once()


def test_get_context_does_not_create_default_file_if_exists(
    service: IGetContextUseCase,
    mock_fs,
    mock_tree_gen,
    mock_inspector,
):
    """
    Tests that get_context does NOT try to create the default context file
    if the permanent context file already exists.
    """
    # Arrange
    mock_fs.path_exists.return_value = True
    # Mock other calls to prevent errors
    mock_tree_gen.generate_tree.return_value = ""
    mock_inspector.get_environment_info.return_value = {}
    mock_fs.get_context_paths.return_value = []
    mock_fs.read_files_in_vault.return_value = {}

    # Act
    service.get_context()

    # Assert
    mock_fs.path_exists.assert_called_once_with(".teddy/init.context")
    mock_fs.create_default_context_file.assert_not_called()


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
    mock_repo_tree = "dir/\n  file.txt"
    mock_vault_paths = ["file1.txt", "file2.py"]
    mock_file_contents = {"file1.txt": "content1", "file2.py": "print('hello')"}

    mock_inspector.get_environment_info.return_value = mock_sys_info
    mock_tree_gen.generate_tree.return_value = mock_repo_tree
    mock_fs.get_context_paths.return_value = mock_vault_paths
    mock_fs.read_files_in_vault.return_value = mock_file_contents

    # Act
    result = service.get_context()

    # Assert
    # Check that dependencies were called correctly
    mock_inspector.get_environment_info.assert_called_once()
    mock_tree_gen.generate_tree.assert_called_once()
    mock_fs.get_context_paths.assert_called_once()
    mock_fs.read_files_in_vault.assert_called_once_with(mock_vault_paths)

    # Check the type of the returned DTO
    assert isinstance(result, ProjectContext)

    # Check header content
    assert "os_name: test_os" in result.header
    assert "shell: /bin/test" in result.header
    assert "cwd: /test/dir" in result.header

    # Check main content
    assert mock_repo_tree in result.content
    assert "[file1.txt](/file1.txt)" in result.content
    assert "```txt\ncontent1\n```" in result.content
    assert "[file2.py](/file2.py)" in result.content
    assert "```py\nprint('hello')\n```" in result.content
