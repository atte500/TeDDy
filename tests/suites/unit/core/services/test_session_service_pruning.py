import pytest
from pathlib import Path
from unittest.mock import ANY
from tests.harness.setup.mocking import register_mock
from teddy_executor.core.services.session_service import SessionService
from teddy_executor.core.services.prompt_manager import PromptManager
from teddy_executor.core.domain.models.session import SessionOptions
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.session_repository import ISessionRepository
from teddy_executor.core.ports.outbound.time_service import ITimeService
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
from teddy_executor.core.ports.inbound.init import IInitUseCase


@pytest.fixture
def mock_deps(container):
    from tests.harness.setup.mocking import register_mock

    return {
        "fsm": register_mock(container, IFileSystemManager),
        "repo": register_mock(container, ISessionRepository),
        "time": register_mock(container, ITimeService),
        "prompt": register_mock(container, IPromptManager),
        "init": register_mock(container, IInitUseCase),
    }


@pytest.fixture
def service(mock_deps):
    return SessionService(
        file_system_manager=mock_deps["fsm"],
        repository=mock_deps["repo"],
        time_service=mock_deps["time"],
        prompt_manager=mock_deps["prompt"],
        init_service=mock_deps["init"],
    )


def test_create_session_does_not_put_prompt_in_turn_directory(service, mock_deps):
    # Arrange
    options = SessionOptions(name="test-session", agent_name="pathfinder")
    mock_deps["prompt"].get_prompt_content.return_value = "<prompt>content</prompt>"
    mock_deps["fsm"].path_exists.return_value = True
    mock_deps["fsm"].read_file.return_value = "README.md"

    # Act
    session_root = service.create_session(options)

    # Assert
    # We expect it at session root
    expected_root_prompt = f"{session_root}/pathfinder.xml"
    mock_deps["fsm"].write_file.assert_any_call(
        expected_root_prompt, "<prompt>content</prompt>"
    )

    # We strictly FORBID it in the turn directory (01)
    forbidden_turn_prompt = f"{session_root}/01/pathfinder.xml"

    # Check all write_file calls
    write_paths = [call.args[0] for call in mock_deps["fsm"].write_file.call_args_list]
    assert forbidden_turn_prompt not in write_paths, (
        "Prompt should not be written to turn directory"
    )


def test_migration_does_not_clone_prompt_into_new_turn_directory(service, mock_deps):
    # Arrange: Scenario where we are at turn 99 and transition
    cur_plan_path = ".teddy/sessions/my-session/99/plan.md"
    mock_deps["repo"].load_meta.return_value = {
        "turn_id": "99",
        "agent_name": "pathfinder",
        "cumulative_cost": 1.0,
    }
    # Mocking the filesystem for migration
    mock_deps["fsm"].path_exists.return_value = True

    # Act
    service.transition_to_next_turn(cur_plan_path)

    # Assert
    # Session root for the new session should have the prompt
    # But the turn directory (01) should NOT
    forbidden_turn_prompt = ".teddy/sessions/my-session-2/01/pathfinder.xml"
    write_paths = [call.args[0] for call in mock_deps["fsm"].write_file.call_args_list]

    assert forbidden_turn_prompt not in write_paths, (
        "Prompt should not be cloned into turn directory during migration"
    )


def test_transition_does_not_put_prompt_in_turn_directory(service, mock_deps):
    # Arrange
    cur_plan_path = ".teddy/sessions/my-session/01/plan.md"
    mock_deps["repo"].load_meta.return_value = {
        "turn_id": "01",
        "agent_name": "pathfinder",
        "cumulative_cost": 0.1,
    }
    mock_deps["repo"].read_context_file.return_value = set()
    mock_deps["repo"].to_root_relative.return_value = "01/plan.md"

    # Act
    service.transition_to_next_turn(cur_plan_path)

    # Assert
    forbidden_turn_prompt = ".teddy/sessions/my-session/02/pathfinder.xml"
    write_paths = [call.args[0] for call in mock_deps["fsm"].write_file.call_args_list]
    assert forbidden_turn_prompt not in write_paths, (
        "Prompt should not be written to turn 02 directory"
    )


def test_migration_99_to_01_does_not_put_prompt_in_turn_directory(service, mock_deps):
    # Arrange
    cur_plan_path = ".teddy/sessions/my-session/99/plan.md"
    mock_deps["repo"].load_meta.return_value = {
        "turn_id": "99",
        "agent_name": "pathfinder",
        "cumulative_cost": 4.5,
    }
    mock_deps["repo"].read_context_file.return_value = set()
    mock_deps["repo"].to_root_relative.return_value = "99/plan.md"
    mock_deps["fsm"].path_exists.return_value = True

    # Act
    service.transition_to_next_turn(cur_plan_path)

    # Assert
    # We expect prompt at the NEW session root
    expected_new_root_prompt = ".teddy/sessions/my-session-2/pathfinder.xml"
    mock_deps["fsm"].write_file.assert_any_call(expected_new_root_prompt, ANY)

    # We strictly FORBID it in the NEW Turn 01 directory
    forbidden_turn_prompt = ".teddy/sessions/my-session-2/01/pathfinder.xml"
    write_paths = [call.args[0] for call in mock_deps["fsm"].write_file.call_args_list]
    assert forbidden_turn_prompt not in write_paths, (
        "Prompt should not be cloned into NEW turn 01 directory during migration"
    )


def test_prompt_manager_ignores_turn_local_override(container):
    # Arrange

    fsm = register_mock(container, IFileSystemManager)
    pm = PromptManager(file_system_manager=fsm)
    turn_path = Path("session/01")
    agent = "pathfinder"

    # Mock behavior:
    # Session root check -> False
    # Turn dir check -> True
    # Resource check -> False
    fsm.path_exists.side_effect = lambda p: "session/01" in p
    fsm.read_file.return_value = "<turn-local-prompt/>"

    # Act
    content = pm.fetch_system_prompt(agent, turn_path)

    # Assert
    assert content == "", "PromptManager should ignore turn-local overrides"
