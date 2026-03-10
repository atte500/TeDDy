import pytest
from pathlib import Path
from unittest.mock import Mock, call
from teddy_executor.core.services.init_service import InitService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager

# Load source files for robust assertions
CONFIG_ROOT = Path(__file__).parents[4] / "config"
SOURCE_CONFIG = (CONFIG_ROOT / "config.yaml").read_text(encoding="utf-8")
SOURCE_CONTEXT = (CONFIG_ROOT / "init.context").read_text(encoding="utf-8")
SOURCE_GITIGNORE = (CONFIG_ROOT / ".gitignore").read_text(encoding="utf-8")


@pytest.fixture
def mock_fs():
    return Mock(spec=IFileSystemManager)


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
    mock_fs.write_file.assert_any_call(".teddy/.gitignore", SOURCE_GITIGNORE)

    # Should check and create config.yaml
    assert call(".teddy/config.yaml") in mock_fs.path_exists.call_args_list
    mock_fs.write_file.assert_any_call(".teddy/config.yaml", SOURCE_CONFIG)

    # Should check and create init.context
    assert call(".teddy/init.context") in mock_fs.path_exists.call_args_list
    mock_fs.write_file.assert_any_call(".teddy/init.context", SOURCE_CONTEXT)


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
    mock_fs.write_file.assert_any_call(".teddy/config.yaml", SOURCE_CONFIG)
    mock_fs.write_file.assert_any_call(".teddy/init.context", SOURCE_CONTEXT)
