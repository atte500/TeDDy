from pathlib import Path

import pytest
from teddy_executor.core.services.init_service import InitService

SOURCE_CONFIG = "mock config content"
SOURCE_CONTEXT = "mock context content"
SOURCE_GITIGNORE = "mock gitignore content"


@pytest.fixture
def service(mock_fs):
    # We use a mock path for config_dir
    return InitService(file_system=mock_fs, config_dir="/mock/config")


def test_ensure_initialized_creates_directory_and_files_if_missing(service, mock_fs):
    # Given
    def mock_exists(p):
        # templates exist, but .teddy does not
        if p.startswith("/mock/config"):
            return True
        return False

    mock_fs.path_exists.side_effect = mock_exists
    mock_fs.read_file.side_effect = lambda p: {
        "/mock/config/.gitignore": SOURCE_GITIGNORE,
        "/mock/config/config.yaml": SOURCE_CONFIG,
        "/mock/config/init.context": SOURCE_CONTEXT,
    }.get(p)

    # When
    service.ensure_initialized()

    # Then
    mock_fs.create_directory.assert_called_once_with(".teddy")
    mock_fs.write_file.assert_any_call(str(Path(".teddy/.gitignore")), SOURCE_GITIGNORE)
    mock_fs.write_file.assert_any_call(str(Path(".teddy/config.yaml")), SOURCE_CONFIG)
    mock_fs.write_file.assert_any_call(str(Path(".teddy/init.context")), SOURCE_CONTEXT)


def test_ensure_initialized_does_not_overwrite_existing_files(service, mock_fs):
    # Given
    mock_fs.path_exists.return_value = True  # Everything exists

    # When
    service.ensure_initialized()

    # Then
    mock_fs.create_directory.assert_not_called()
    mock_fs.write_file.assert_not_called()
