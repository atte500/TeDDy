import pytest
from pathlib import Path
from teddy_executor.core.services.prompt_manager import PromptManager


@pytest.fixture
def prompt_manager(mock_fs, mock_user_interactor):
    return PromptManager(
        file_system_manager=mock_fs, user_interactor=mock_user_interactor
    )


def test_resolve_agent_metadata_returns_defaults_if_file_missing(
    prompt_manager, mock_fs
):
    # Arrange
    mock_fs.path_exists.return_value = False
    turn_path = Path("turns/01")

    # Act
    agent_name, meta, meta_path = prompt_manager.resolve_agent_metadata(turn_path)

    # Assert
    assert agent_name == "pathfinder"
    assert meta == {}
    assert meta_path == "turns/01/meta.yaml"


def test_fetch_system_prompt_resolves_from_teddy_prompts(prompt_manager, mock_fs):
    """
    Verifies that fetch_system_prompt resolves from .teddy/prompts/ when session root
    does not have the prompt, and does NOT fall back to internal bundled resources.
    """
    # Arrange
    turn_path = Path(".teddy/sessions/my-session/01")
    agent_name = "pathfinder"

    # Session root missing, .teddy/prompts/ has it
    def mock_exists(path: str) -> bool:
        if path.endswith("sessions/my-session/pathfinder.xml"):
            return False
        if path.endswith("prompts/pathfinder.xml"):
            return True
        return False

    mock_fs.path_exists.side_effect = mock_exists
    mock_fs.read_file.side_effect = lambda p: {
        ".teddy/prompts/pathfinder.xml": "<prompt>From .teddy/prompts/</prompt>",
    }.get(p, "")

    # Act
    content = prompt_manager.fetch_system_prompt(agent_name, turn_path)

    # Assert
    assert content == "<prompt>From .teddy/prompts/</prompt>"


def test_get_available_agents_returns_xml_files(prompt_manager, mock_fs):
    """
    Verifies that get_available_agents() lists .xml files from .teddy/prompts/
    and returns agent names stripped of the .xml extension.
    """
    # Arrange
    mock_fs.path_exists.return_value = True
    mock_fs.list_directory.return_value = [
        "architect.xml",
        "developer.xml",
        "pathfinder.xml",
    ]

    # Act
    agents = prompt_manager.get_available_agents()

    # Assert
    assert agents == ["architect", "developer", "pathfinder"]
    mock_fs.path_exists.assert_called_once_with(".teddy/prompts/")
    mock_fs.list_directory.assert_called_once_with(".teddy/prompts/")


def test_get_available_agents_returns_empty_when_directory_missing(
    prompt_manager, mock_fs
):
    """
    Verifies that get_available_agents() returns an empty list when
    .teddy/prompts/ does not exist.
    """
    # Arrange
    mock_fs.path_exists.return_value = False

    # Act
    agents = prompt_manager.get_available_agents()

    # Assert
    assert agents == []
    mock_fs.path_exists.assert_called_once_with(".teddy/prompts/")


def test_get_available_agents_filters_non_xml_files(prompt_manager, mock_fs):
    """
    Verifies that get_available_agents() only returns .xml files,
    filtering out non-xml files like README.md and notes.txt.
    """
    # Arrange
    mock_fs.path_exists.return_value = True
    mock_fs.list_directory.return_value = [
        "architect.xml",
        "README.md",
        "debugger.xml",
        "pathfinder.xml",
        "notes.txt",
    ]

    # Act
    agents = prompt_manager.get_available_agents()

    # Assert
    assert agents == ["architect", "debugger", "pathfinder"]
