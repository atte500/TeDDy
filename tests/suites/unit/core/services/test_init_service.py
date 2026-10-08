import pytest
from teddy_executor.core.services.init_service import (
    InitService,
    _GITIGNORE_PLACEHOLDER,
    _TEMPLATE_FILES,
)

SOURCE_CONFIG = "mock config content"
SOURCE_CONTEXT = "mock context content"


@pytest.fixture
def service(mock_fs):
    # We use a mock path for config_dir
    return InitService(file_system=mock_fs, config_dir="/mock/config")


@pytest.fixture
def templates_service(mock_fs):
    # Mock templates_dir to isolate file-system interaction for template tests.
    return InitService(
        file_system=mock_fs,
        config_dir="/mock/config",
        templates_dir="/mock/templates",
    )


def test_ensure_initialized_creates_directory_and_files_if_missing(service, mock_fs):
    # Given
    def mock_exists(p):
        # templates exist, but .teddy does not
        if p.startswith("/mock/config"):
            return True
        return False

    mock_fs.path_exists.side_effect = mock_exists
    mock_fs.read_file.side_effect = lambda p: {
        "/mock/config/config.yaml": SOURCE_CONFIG,
        "/mock/config/init.context": SOURCE_CONTEXT,
    }.get(p)

    # When
    service.ensure_initialized()

    # Then
    mock_fs.create_directory.assert_any_call(".teddy")
    mock_fs.create_directory.assert_any_call(".teddy/prompts")
    # The .gitignore scaffold comes from an embedded constant, not a template file.
    mock_fs.write_file.assert_any_call(".teddy/.gitignore", _GITIGNORE_PLACEHOLDER)
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
    mock_fs.write_file.assert_any_call(".teddy/.gitignore", _GITIGNORE_PLACEHOLDER)
    mock_fs.write_file.assert_any_call(".teddy/config.yaml", "mock config")
    mock_fs.write_file.assert_any_call(".teddy/init.context", "mock context")
    for fname in PROMPT_FILES:
        prompt_name = fname.replace(".xml", "")
        expected_content = f"{prompt_name} prompt"
        mock_fs.write_file.assert_any_call(f".teddy/prompts/{fname}", expected_content)


# ── New tests for overwrite flags and summary strings ────────────────────────


def test_ensure_initialized_returns_summary_when_everything_exists(service, mock_fs):
    """All files exist → "Config: unchanged. Prompts: unchanged. Templates: unchanged." """
    mock_fs.path_exists.return_value = True  # Everything exists
    result = service.ensure_initialized()
    mock_fs.write_file.assert_not_called()
    assert result == ("Config: unchanged. Prompts: unchanged. Templates: unchanged.")


def test_ensure_initialized_returns_summary_when_files_missing(service, mock_fs):
    """Missing .teddy files → config/prompts updated; templates unchanged.

    The ``service`` fixture sets no ``templates_dir``, so the template resources
    live outside the mocked ``/mock/config`` tree and resolve to None; the
    templates segment therefore reports "unchanged".
    """

    def mock_exists(p):
        # config templates exist, but .teddy does not
        if p.startswith("/mock/config"):
            return True
        return False

    mock_fs.path_exists.side_effect = mock_exists
    mock_fs.read_file.return_value = "mock content"

    result = service.ensure_initialized()
    assert result == (
        "Config: updated (4 files). Prompts: updated (6 files). Templates: unchanged."
    )


def test_ensure_prompts_initialized_overwrite_true(service, mock_fs):
    """All prompts exist, but overwrite=True → overwrites all 6 and returns "Prompts overwritten (6 files)." """

    def mock_exists(p):
        if p.startswith("/mock/config"):
            return True
        return True  # everything else also exists

    mock_fs.path_exists.side_effect = mock_exists
    mock_fs.read_file.return_value = "mock content"

    result = service.ensure_prompts_initialized(overwrite=True)
    assert mock_fs.write_file.call_count == 6
    assert result == "Prompts overwritten (6 files)."


def test_ensure_prompts_initialized_overwrite_false(service, mock_fs):
    """All prompts exist, overwrite=False → nothing written, returns "Prompts unchanged." """
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = "mock content"

    result = service.ensure_prompts_initialized(overwrite=False)
    mock_fs.write_file.assert_not_called()
    assert result == "Prompts unchanged."


def test_ensure_prompts_initialized_missing_prompts_non_overwrite(service, mock_fs):
    """No prompts exist, overwrite=False → write 6, returns "Prompts updated (6 files)." """

    def mock_exists(p):
        if p.startswith("/mock/config"):
            return True
        return False  # nothing exists in .teddy

    mock_fs.path_exists.side_effect = mock_exists
    mock_fs.read_file.return_value = "mock content"

    result = service.ensure_prompts_initialized(overwrite=False)
    assert mock_fs.write_file.call_count == 6
    assert result == "Prompts updated (6 files)."


def test_ensure_config_initialized_overwrite_true(service, mock_fs):
    """All config exist, overwrite=True → overwrites the 3 regenerable files
    (config.yaml, .gitignore, init.context) and PRESERVES the existing `.env`."""
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = "mock content"

    result = service.ensure_config_initialized(overwrite=True)

    written_paths = [call.args[0] for call in mock_fs.write_file.call_args_list]
    assert mock_fs.write_file.call_count == 3
    assert set(written_paths) == {
        ".teddy/config.yaml",
        ".teddy/.gitignore",
        ".teddy/init.context",
    }
    assert ".teddy/.env" not in written_paths
    assert result == "Configuration files overwritten (3 files)."


def test_ensure_config_initialized_overwrite_false(service, mock_fs):
    """All config exist, overwrite=False → nothing written, returns "Configuration files unchanged." """
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = "mock content"

    result = service.ensure_config_initialized(overwrite=False)
    mock_fs.write_file.assert_not_called()
    assert result == "Configuration files unchanged."


def test_ensure_config_initialized_missing_config_non_overwrite(service, mock_fs):
    """No config files exist, overwrite=False → write 4, returns "Configuration files updated (4 files)." """

    def mock_exists(p):
        if p.startswith("/mock/config"):
            return True
        return False

    mock_fs.path_exists.side_effect = mock_exists
    mock_fs.read_file.return_value = "mock content"

    result = service.ensure_config_initialized(overwrite=False)
    assert mock_fs.write_file.call_count == 4
    assert result == "Configuration files updated (4 files)."


def test_ensure_config_initialized_scaffolds_env_placeholder(service, mock_fs):
    """`teddy init config` scaffolds a commented `.teddy/.env` placeholder.

    The placeholder gives the user a file to paste the LLM API key into; the
    bundled `config.yaml` already references the value via the
    ``${TEDDY_LLM_API_KEY}`` interpolation token.
    """

    def mock_exists(p):
        if p.startswith("/mock/config"):
            return True
        return False

    mock_fs.path_exists.side_effect = mock_exists
    mock_fs.read_file.return_value = "mock content"

    # Act
    service.ensure_config_initialized(overwrite=False)

    # Assert - the .env placeholder is scaffolded alongside the other files
    written = {call.args[0]: call.args[1] for call in mock_fs.write_file.call_args_list}
    assert ".teddy/.env" in written
    assert "TEDDY_LLM_API_KEY" in written[".teddy/.env"]
    # The key line is uncommented so dotenv.set_key rewrites it in place
    # rather than appending a second line next to a dead comment.
    assert "\nTEDDY_LLM_API_KEY=\n" in written[".teddy/.env"]
    assert "# TEDDY_LLM_API_KEY=" not in written[".teddy/.env"]


def test_ensure_config_initialized_overwrite_true_creates_missing_env(service, mock_fs):
    """Create-only ≠ never-create: `overwrite=True` still scaffolds `.env` when absent."""

    def mock_exists(p):
        if p.startswith("/mock/config"):
            return True
        # Only `.env` is missing; the three regenerable files already exist.
        return p != ".teddy/.env"

    mock_fs.path_exists.side_effect = mock_exists
    mock_fs.read_file.return_value = "mock content"

    service.ensure_config_initialized(overwrite=True)

    written = {call.args[0]: call.args[1] for call in mock_fs.write_file.call_args_list}
    assert ".teddy/.env" in written
    assert "TEDDY_LLM_API_KEY" in written[".teddy/.env"]
    assert ".teddy/config.yaml" in written


# ── Template initialization tests ────────────────────────────────────────────


def test_init_templates_copies_all_when_missing(templates_service, mock_fs):
    """No docs/templates/ exists, overwrite=False → creates dir and writes all 11 templates."""

    def mock_exists(p: str) -> bool:
        # Bundled templates exist; docs/templates/ does not.
        return p.startswith("/mock/templates")

    mock_fs.path_exists.side_effect = mock_exists
    mock_fs.read_file.side_effect = lambda p: f"content::{p}"

    result = templates_service._init_templates(overwrite=False)

    mock_fs.create_directory.assert_any_call("docs/templates")
    for fname in _TEMPLATE_FILES:
        mock_fs.write_file.assert_any_call(
            f"docs/templates/{fname}", f"content::/mock/templates/{fname}"
        )
    assert mock_fs.write_file.call_count == 11
    assert result == "updated (11 files)"


def test_init_templates_partial_population_non_destructive(templates_service, mock_fs):
    """Some templates already exist, overwrite=False → only missing ones are written."""

    existing = {"specification-document.md", "task-brief.md"}

    def mock_exists(p: str) -> bool:
        if p.startswith("/mock/templates"):
            return True
        if p == "docs/templates":
            return True
        return p in {f"docs/templates/{fname}" for fname in existing}

    mock_fs.path_exists.side_effect = mock_exists
    mock_fs.read_file.side_effect = lambda p: f"content::{p}"

    result = templates_service._init_templates(overwrite=False)

    written = [call.args[0] for call in mock_fs.write_file.call_args_list]
    assert mock_fs.write_file.call_count == len(_TEMPLATE_FILES) - len(existing)
    for fname in existing:
        assert f"docs/templates/{fname}" not in written
    assert result == f"updated ({len(_TEMPLATE_FILES) - len(existing)} files)"


def test_init_templates_overwrite_true_replaces(templates_service, mock_fs):
    """All templates already exist, overwrite=True → all are rewritten."""

    def mock_exists(p: str) -> bool:
        # Bundled templates AND every docs/templates/ target already exist.
        return True

    mock_fs.path_exists.side_effect = mock_exists
    mock_fs.read_file.side_effect = lambda p: f"content::{p}"

    result = templates_service._init_templates(overwrite=True)

    assert mock_fs.write_file.call_count == len(_TEMPLATE_FILES)
    assert result == f"overwritten ({len(_TEMPLATE_FILES)} files)"


def test_init_templates_missing_resource_no_op(templates_service, mock_fs):
    """Bundled templates resource is missing → no writes, returns "unchanged"."""

    mock_fs.path_exists.return_value = False

    result = templates_service._init_templates(overwrite=False)

    mock_fs.write_file.assert_not_called()
    assert result == "unchanged"


def test_ensure_templates_initialized_returns_status(templates_service, mock_fs):
    """`ensure_templates_initialized` wraps `_init_templates` with a "Templates" prefix."""

    def mock_exists(p: str) -> bool:
        # Bundled templates exist; docs/templates/ does not.
        return p.startswith("/mock/templates")

    mock_fs.path_exists.side_effect = mock_exists
    mock_fs.read_file.side_effect = lambda p: f"content::{p}"

    result = templates_service.ensure_templates_initialized(overwrite=False)

    assert result == f"Templates updated ({len(_TEMPLATE_FILES)} files)."
