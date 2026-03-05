import pytest
from unittest.mock import Mock, call
from teddy_executor.core.services.init_service import (
    InitService,
    DEFAULT_CONFIG_YAML,
    DEFAULT_INIT_CONTEXT,
)
from teddy_executor.core.ports.outbound.file_system_manager import FileSystemManager


@pytest.fixture
def mock_fs():
    return Mock(spec=FileSystemManager)


@pytest.fixture
def service(mock_fs):
    return InitService(file_system=mock_fs)


def test_ensure_initialized_creates_directory_and_files_if_missing(service, mock_fs):
    # Given
    mock_fs.path_exists.side_effect = lambda p: False  # Nothing exists

    # When
    service.ensure_initialized()

    # Then
    # Should check and create the .teddy directory
    assert call(".teddy") in mock_fs.path_exists.call_args_list
    mock_fs.create_directory.assert_called_once_with(".teddy")

    # Should check and create .gitignore
    assert call(".teddy/.gitignore") in mock_fs.path_exists.call_args_list
    mock_fs.write_file.assert_any_call(".teddy/.gitignore", "*")

    # Should check and create config.yaml
    assert call(".teddy/config.yaml") in mock_fs.path_exists.call_args_list
    mock_fs.write_file.assert_any_call(".teddy/config.yaml", DEFAULT_CONFIG_YAML)

    # Should check and create init.context
    assert call(".teddy/init.context") in mock_fs.path_exists.call_args_list
    mock_fs.write_file.assert_any_call(".teddy/init.context", DEFAULT_INIT_CONTEXT)


def test_ensure_initialized_does_not_overwrite_existing_files(service, mock_fs):
    # Given
    mock_fs.path_exists.side_effect = lambda p: True  # Everything exists

    # When
    service.ensure_initialized()

    # Then
    mock_fs.create_directory.assert_not_called()
    mock_fs.write_file.assert_not_called()


def test_ensure_initialized_handles_partial_initialization(service, mock_fs):
    """
    Scenario: Partial initialization
    - Given a workspace with a .teddy/ directory but no config.yaml.
    """
    # Given: .teddy exists, but config.yaml and init.context do not.
    existence_map = {
        ".teddy": True,
        ".teddy/config.yaml": False,
        ".teddy/init.context": False,
    }
    mock_fs.path_exists.side_effect = lambda p: existence_map.get(p, False)

    # When
    service.ensure_initialized()

    # Then: Should NOT try to create the directory again
    mock_fs.create_directory.assert_not_called()

    # Should create missing files
    mock_fs.write_file.assert_any_call(".teddy/config.yaml", DEFAULT_CONFIG_YAML)
    mock_fs.write_file.assert_any_call(".teddy/init.context", DEFAULT_INIT_CONTEXT)
