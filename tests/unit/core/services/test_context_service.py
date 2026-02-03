import pytest
from unittest.mock import MagicMock, call, Mock

from teddy_executor.core.services.context_service import ContextService


@pytest.fixture
def mock_file_system_manager() -> Mock:
    return MagicMock()


@pytest.fixture
def mock_repo_tree_generator() -> Mock:
    return MagicMock()


@pytest.fixture
def mock_environment_inspector() -> Mock:
    return MagicMock()


@pytest.fixture
def service(
    mock_file_system_manager: Mock,
    mock_repo_tree_generator: Mock,
    mock_environment_inspector: Mock,
) -> ContextService:
    """Provides a ContextService instance with mocked dependencies."""
    return ContextService(
        file_system_manager=mock_file_system_manager,
        repo_tree_generator=mock_repo_tree_generator,
        environment_inspector=mock_environment_inspector,
    )


def test_get_context_creates_default_file_if_not_exists(
    service: ContextService,
    mock_file_system_manager: Mock,
    mock_repo_tree_generator: Mock,
    mock_environment_inspector: Mock,
):
    """
    Scenario: Simplified Default Configuration (Service Level)
    Tests that get_context calls the file system manager to create the
    default context file if the permanent context file does not exist.
    """
    # Arrange
    mock_file_system_manager.path_exists.return_value = False

    # Mock return values for the rest of the function to avoid subsequent errors
    mock_repo_tree_generator.generate_tree.return_value = ""
    mock_environment_inspector.get_environment_info.return_value = {}
    mock_file_system_manager.get_context_paths.return_value = []
    mock_file_system_manager.read_files_in_vault.return_value = {}

    # Act
    service.get_context()

    # Assert
    mock_file_system_manager.path_exists.assert_called_once_with(".teddy/perm.context")
    mock_file_system_manager.create_default_context_file.assert_called_once()


def test_get_context_does_not_create_default_file_if_exists(
    service: ContextService,
    mock_file_system_manager: Mock,
    mock_repo_tree_generator: Mock,
    mock_environment_inspector: Mock,
):
    """
    Tests that get_context does NOT try to create the default context file
    if the permanent context file already exists.
    """
    # Arrange
    mock_file_system_manager.path_exists.return_value = True
    # Mock other calls to prevent errors
    mock_repo_tree_generator.generate_tree.return_value = ""
    mock_environment_inspector.get_environment_info.return_value = {}
    mock_file_system_manager.get_context_paths.return_value = []
    mock_file_system_manager.read_files_in_vault.return_value = {}

    # Act
    service.get_context()

    # Assert
    mock_file_system_manager.path_exists.assert_called_once_with(".teddy/perm.context")
    mock_file_system_manager.create_default_context_file.assert_not_called()


def test_get_context_orchestrates_and_returns_correct_dto(
    service: ContextService,
    mock_file_system_manager: Mock,
    mock_repo_tree_generator: Mock,
    mock_environment_inspector: Mock,
):
    """
    Scenario: Standardized Output Format (Service Level)
    Tests that get_context calls all its dependencies correctly and assembles
    the ContextResult DTO with the data they provide.
    """
    # Arrange
    # Simulate existing perm.context file
    mock_file_system_manager.path_exists.return_value = True

    # Mock data from dependencies
    mock_sys_info = {"os": "test_os", "shell": "/bin/test"}
    mock_repo_tree = "dir/\n  file.txt"
    mock_vault_paths = ["file1.txt", "file2.txt"]
    mock_file_contents = {"file1.txt": "content1", "file2.txt": "content2"}

    mock_environment_inspector.get_environment_info.return_value = mock_sys_info
    mock_repo_tree_generator.generate_tree.return_value = mock_repo_tree
    mock_file_system_manager.get_context_paths.return_value = mock_vault_paths
    mock_file_system_manager.read_files_in_vault.return_value = mock_file_contents

    # Act
    result = service.get_context()

    # Assert
    # Check that dependencies were called correctly
    mock_environment_inspector.get_environment_info.assert_called_once()
    mock_repo_tree_generator.generate_tree.assert_called_once()
    mock_file_system_manager.get_context_paths.assert_called_once()
    mock_file_system_manager.read_files_in_vault.assert_called_once_with(
        mock_vault_paths
    )

    # Check that the service does NOT write a repotree.txt file anymore
    assert (
        call(".teddy/repotree.txt")
        not in mock_file_system_manager.write_file.call_args_list
    )

    # Check the contents of the returned DTO
    assert result.system_info == mock_sys_info
    assert result.repo_tree == mock_repo_tree
    assert result.context_vault_paths == mock_vault_paths
    assert result.file_contents == mock_file_contents
