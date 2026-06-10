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
    mock_fs.create_directory.assert_any_call(".teddy")
    mock_fs.create_directory.assert_any_call(".teddy/prompts")
    # Ensure we use the exact content from side_effect for assertions
    mock_fs.write_file.assert_any_call(".teddy/.gitignore", SOURCE_GITIGNORE)
    mock_fs.write_file.assert_any_call(".teddy/config.yaml", SOURCE_CONFIG)
    mock_fs.write_file.assert_any_call(".teddy/init.context", SOURCE_CONTEXT)


def test_ensure_initialized_does_not_overwrite_existing_files(service, mock_fs):
    # Given
    mock_fs.path_exists.return_value = True  # Everything exists

    # When
    service.ensure_initialized()

    # Then
    mock_fs.create_directory.assert_not_called()
    mock_fs.write_file.assert_not_called()


def test_init_service_default_path_resolution(mock_fs):
    """
    Verifies that the default constructor resolves to the package resources.
    This test will fail if the relative path is broken.
    """
    # Given
    service = InitService(file_system=mock_fs)

    # Then
    # The resolved path should now be inside the package structure,
    # no longer pointing to the root 'config' directory.
    assert "src/teddy_executor/resources/config" in service._config_dir.replace(
        "\\", "/"
    )


PROMPT_FILES = [
    "architect.xml",
    "assistant.xml",
    "debugger.xml",
    "developer.xml",
    "pathfinder.xml",
    "prototyper.xml",
]


def test_ensure_initialized_copies_prompts_to_teddy(service, mock_fs):
    """Verifies that ensure_initialized copies prompt XMLs to .teddy/prompts/."""

    # Given
    def mock_exists(p: str) -> bool:
        # Bundled config resources exist
        if p.startswith("/mock/config"):
            return True
        # .teddy does not exist (prompts copy should run)
        return False

    mock_fs.path_exists.side_effect = mock_exists

    def mock_read(p: str) -> str:
        return {
            "/mock/config/.gitignore": "mock gitignore",
            "/mock/config/config.yaml": "mock config",
            "/mock/config/init.context": "mock context",
            "/mock/config/prompts/architect.xml": "architect prompt",
            "/mock/config/prompts/assistant.xml": "assistant prompt",
            "/mock/config/prompts/debugger.xml": "debugger prompt",
            "/mock/config/prompts/developer.xml": "developer prompt",
            "/mock/config/prompts/pathfinder.xml": "pathfinder prompt",
            "/mock/config/prompts/prototyper.xml": "prototyper prompt",
        }.get(p, "")

    mock_fs.read_file.side_effect = mock_read

    # When
    service.ensure_initialized()

    # Then
    mock_fs.create_directory.assert_any_call(".teddy")
    mock_fs.write_file.assert_any_call(".teddy/.gitignore", "mock gitignore")
    mock_fs.write_file.assert_any_call(".teddy/config.yaml", "mock config")
    mock_fs.write_file.assert_any_call(".teddy/init.context", "mock context")
    for fname in PROMPT_FILES:
        prompt_name = fname.replace(".xml", "")
        expected_content = f"{prompt_name} prompt"
        mock_fs.write_file.assert_any_call(f".teddy/prompts/{fname}", expected_content)
