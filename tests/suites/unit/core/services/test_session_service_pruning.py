import pytest
from pathlib import Path
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
    from teddy_executor.core.ports.outbound.config_service import IConfigService

    fsm = register_mock(container, IFileSystemManager)
    # Default read_file to a valid non-message plan so _is_preserved_turn()
    # doesn't receive a MagicMock and can properly check patterns.
    fsm.read_file.return_value = "# Test Plan\n## Action Plan\n\nSome actions\n"

    return {
        "fsm": fsm,
        "repo": register_mock(container, ISessionRepository),
        "time": register_mock(container, ITimeService),
        "prompt": register_mock(container, IPromptManager),
        "init": register_mock(container, IInitUseCase),
        "config": register_mock(container, IConfigService),
    }


@pytest.fixture
def service(mock_deps):
    return SessionService(
        file_system_manager=mock_deps["fsm"],
        repository=mock_deps["repo"],
        time_service=mock_deps["time"],
        prompt_manager=mock_deps["prompt"],
        init_service=mock_deps["init"],
        config_service=mock_deps["config"],
    )


def test_create_session_does_not_put_prompt_in_turn_directory(service, mock_deps):
    # Arrange
    options = SessionOptions(name="test-session", agent_name="pathfinder")
    mock_deps["fsm"].path_exists.return_value = True
    mock_deps["fsm"].list_directory.side_effect = lambda d: {
        ".teddy/prompts": [f"{options.agent_name}.xml"],
    }.get(d, [])
    mock_deps["fsm"].read_file.side_effect = lambda p: {
        ".teddy/init.context": "README.md",
        f".teddy/prompts/{options.agent_name}.xml": "<prompt>content</prompt>",
    }.get(p, "")
    # Option A: create_session persists the COMPOSED system prompt returned by
    # the prompt manager at the session root.
    composed_prompt = (
        "Agent Name: Pathfinder\n\n<prompt>content</prompt>\n\n"
        "<mrp>SHARED_PROTOCOL</mrp>"
    )
    mock_deps["prompt"].fetch_system_prompt.return_value = composed_prompt

    # Act
    session_root = service.create_session(options)

    # Assert
    # We expect it at session root
    expected_root_prompt = f"{session_root}/pathfinder.xml"
    mock_deps["fsm"].write_file.assert_any_call(expected_root_prompt, composed_prompt)

    # We strictly FORBID it in the turn directory (01)
    forbidden_turn_prompt = f"{session_root}/01/pathfinder.xml"

    # Check all write_file calls
    write_paths = [call.args[0] for call in mock_deps["fsm"].write_file.call_args_list]
    assert forbidden_turn_prompt not in write_paths, (
        "Prompt should not be written to turn directory"
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


def test_set_session_agent_persists_recomposed_prompt_at_session_root(
    service, mock_deps
):
    """set_session_agent persists the RECOMPOSED system prompt on agent switch.

    Option A: switching agents must recompose (agent-name header + agent XML +
    MRP) and persist that composed prompt to the session root -- never the raw
    ``.teddy/prompts/`` content -- so later turns reuse it verbatim.
    """
    # Arrange
    session_name = "test-recompose"
    session_root = f".teddy/sessions/{session_name}"
    latest_turn_path = f"{session_root}/03"

    mock_deps["repo"].get_latest_turn.return_value = latest_turn_path
    mock_deps["repo"].load_meta.return_value = {
        "agent_name": "pathfinder",
        "turn_id": "03",
    }
    mock_deps["repo"].to_root_relative.return_value = "test.xml"

    composed = (
        "Agent Name: Developer\n\n"
        "<prompt>developer content</prompt>\n\n"
        "<mrp>SHARED_PROTOCOL</mrp>"
    )
    mock_deps["prompt"].fetch_system_prompt.return_value = composed

    mock_deps["fsm"].path_exists.side_effect = lambda p: (
        p
        in {
            ".teddy/prompts",
            ".teddy/prompts/Developer.xml",
        }
    )
    mock_deps["fsm"].list_directory.side_effect = lambda d: {
        ".teddy/prompts": ["architect.xml", "Developer.xml"],
        session_root: ["pathfinder.xml", "turn.context"],
    }.get(d, [])
    mock_deps["fsm"].read_file.side_effect = lambda p: {
        ".teddy/prompts/Developer.xml": "<prompt>developer content</prompt>",
    }.get(p, "")

    # Act
    service.set_session_agent(session_name, "developer")

    # Assert: the COMPOSED prompt was persisted, not the raw content
    prompt_path = f"{session_root}/Developer.xml"
    mock_deps["fsm"].write_file.assert_any_call(prompt_path, composed)

    written = {
        call.args[0]: call.args[1]
        for call in mock_deps["fsm"].write_file.call_args_list
    }
    assert written[prompt_path] != "<prompt>developer content</prompt>"

    # Composition is delegated to the prompt manager exactly once
    mock_deps["prompt"].fetch_system_prompt.assert_called_once()


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
