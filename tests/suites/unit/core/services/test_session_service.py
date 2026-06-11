import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import ANY

from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.domain.models.session import SessionOptions
from teddy_executor.core.ports.outbound.time_service import ITimeService
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager


def test_create_session_orchestrates_filesystem_correctly(env):
    """
    Tests that create_session creates the correct directory structure and files.
    """
    # Arrange
    mock_time = env.mock_port(ITimeService)
    mock_prompts = env.mock_port(IPromptManager)
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()

    session_name = "feat-x"
    agent_name = "pathfinder"
    # Include a comment to test stripping
    init_context = "README.md\n# comment\ndocs/project/PROJECT.md"
    clean_context = "README.md\ndocs/project/PROJECT.md"
    agent_prompt = "<prompt>Pathfinder content</prompt>"

    # read_file must return different content based on path
    mock_fs.read_file.side_effect = lambda p: {
        ".teddy/init.context": init_context,
        f".teddy/prompts/{agent_name}.xml": agent_prompt,
    }.get(p, "")
    mock_fs.path_exists.return_value = True
    mock_time.now.return_value = datetime(2026, 4, 17, 12, 0, 0)
    # Mock UTC time for metadata
    mock_time.now_utc.return_value = datetime(2026, 4, 17, 12, 0, 0)
    # Ensure get_prompt_content is NOT called by the new code
    mock_prompts.get_prompt_content.side_effect = AssertionError(
        "create_session should not call get_prompt_content anymore"
    )

    # Act
    service.create_session(
        SessionOptions(
            name=session_name,
            agent_name=agent_name,
            additional_context=["extra.md"],
            model="gpt-4",
        )
    )

    # Assert
    # 1. Directory creation
    mock_fs.create_directory.assert_any_call(
        Path(".teddy/sessions/20260417_120000-feat-x/01").as_posix()
    )

    # 2. session.context creation (with comments stripped and extra paths)
    expected_context = f"{clean_context}\nextra.md"
    mock_fs.write_file.assert_any_call(
        Path(".teddy/sessions/20260417_120000-feat-x/session.context").as_posix(),
        expected_context,
    )

    # 3. pathfinder.xml creation
    mock_fs.write_file.assert_any_call(
        Path(".teddy/sessions/20260417_120000-feat-x/pathfinder.xml").as_posix(),
        agent_prompt,
    )

    # 4. meta.yaml creation
    mock_fs.write_file.assert_any_call(
        Path(".teddy/sessions/20260417_120000-feat-x/01/meta.yaml").as_posix(), ANY
    )


def test_create_session_persists_initial_request(env):
    """
    Tests that create_session persists the initial_request to initial_request.md
    at the session root.
    """
    # Arrange
    mock_time = env.mock_port(ITimeService)
    mock_prompts = env.mock_port(IPromptManager)
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()

    session_name = "goal-x"
    agent_name = "pathfinder"
    initial_request = "# My Goal\nDo some coding."
    mock_time.now.return_value = datetime(2026, 5, 15, 10, 0, 0)
    mock_time.now_utc.return_value = datetime(2026, 5, 15, 10, 0, 0)
    # read_file returns init.context by default, prompt path returns prompt content
    mock_fs.read_file.side_effect = lambda p: {
        ".teddy/init.context": "README.md",
        f".teddy/prompts/{agent_name}.xml": "<prompt/>",
    }.get(p, "")
    mock_fs.path_exists.return_value = True
    mock_prompts.get_prompt_content.side_effect = AssertionError(
        "create_session should not call get_prompt_content anymore"
    )

    # Act
    service.create_session(
        SessionOptions(
            name=session_name, agent_name=agent_name, initial_request=initial_request
        )
    )

    # Assert
    expected_path = Path(
        ".teddy/sessions/20260515_100000-goal-x/initial_request.md"
    ).as_posix()
    mock_fs.write_file.assert_any_call(expected_path, initial_request)


def test_create_session_seeds_initial_request_into_session_context(env):
    """
    Tests that create_session appends initial_request.md to session.context.
    """
    # Arrange
    mock_time = env.mock_port(ITimeService)
    mock_prompts = env.mock_port(IPromptManager)
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()

    session_name = "seed-x"
    agent_name = "pathfinder"
    initial_request = "Goal"
    mock_time.now.return_value = datetime(2026, 5, 15, 10, 0, 0)
    mock_time.now_utc.return_value = datetime(2026, 5, 15, 10, 0, 0)
    mock_fs.read_file.side_effect = lambda p: {
        ".teddy/init.context": "README.md",
        f".teddy/prompts/{agent_name}.xml": "<prompt/>",
    }.get(p, "")
    mock_fs.path_exists.return_value = True
    mock_prompts.get_prompt_content.side_effect = AssertionError(
        "create_session should not call get_prompt_content anymore"
    )

    # Act
    service.create_session(
        SessionOptions(
            name=session_name, agent_name=agent_name, initial_request=initial_request
        )
    )

    # Assert
    context_path = ".teddy/sessions/20260515_100000-seed-x/session.context"
    # Systemic Solve: Use find_call_by_path instead of manual call_args_list filtering
    context_call = mock_fs.find_call_by_path("write_file", context_path)
    written_content = context_call.args[1]
    lines = written_content.splitlines()

    assert any(line.endswith("initial_request.md") for line in lines)


def test_transition_to_next_turn_prevents_context_leakage_on_failure(env):
    """
    Ensures that READ actions only update turn.context if they were successful.
    """
    # Arrange
    from teddy_executor.core.domain.models import (
        ActionLog,
        ActionStatus,
        ExecutionReport,
        RunStatus,
        RunSummary,
    )
    from teddy_executor.core.domain.models.plan import ActionData, ActionType
    from teddy_executor.core.ports.outbound.session_repository import ISessionRepository

    service = env.get_service(ISessionManager)
    repo = env.mock_port(ISessionRepository)
    fs = env.get_mock_filesystem()

    plan_path = ".teddy/sessions/my-session/01/plan.md"
    repo.load_meta.return_value = {"turn_id": "01", "agent_name": "pf"}
    repo.read_context_file.return_value = set()
    repo.to_root_relative.side_effect = lambda _dir, name: name
    repo.is_valid_path.return_value = True

    # 1. Success Action: should be added
    success_action = ActionData(
        type=ActionType.READ.value, params={"resource": "success.py"}
    )
    success_log = ActionLog(
        status=ActionStatus.SUCCESS,
        action_type="READ",
        params={"resource": "success.py"},
    )

    # 2. Failed Action: should NOT be added
    failed_action = ActionData(
        type=ActionType.READ.value, params={"resource": "failed.py"}
    )
    failed_log = ActionLog(
        status=ActionStatus.FAILURE,
        action_type="READ",
        params={"resource": "failed.py"},
    )

    # 3. Skipped Action: should NOT be added
    skipped_action = ActionData(
        type=ActionType.READ.value, params={"resource": "skipped.py"}
    )
    skipped_log = ActionLog(
        status=ActionStatus.SKIPPED,
        action_type="READ",
        params={"resource": "skipped.py"},
    )

    # Note: RunSummary still uses datetime, but it's a DTO, not hidden state inside SessionService logic.
    # We keep the import for the DTO setup in this test.
    report = ExecutionReport(
        run_summary=RunSummary(
            status=RunStatus.FAILURE, start_time=datetime.now(), end_time=datetime.now()
        ),
        original_actions=[success_action, failed_action, skipped_action],
        action_logs=[success_log, failed_log, skipped_log],
    )

    # Act
    service.transition_to_next_turn(plan_path=plan_path, execution_report=report)

    # Assert
    # Extract the written turn.context content
    context_write_call = [
        call for call in fs.write_file.call_args_list if "turn.context" in str(call)
    ][0]
    written_context = context_write_call.args[1]
    context_lines = written_context.splitlines()

    assert "success.py" in context_lines
    assert "failed.py" not in context_lines, "Failed READ should not leak into context"
    assert "skipped.py" not in context_lines, (
        "Skipped READ should not leak into context"
    )


def test_apply_execution_effects_adds_create_and_edit_targets(env):
    """
    Ensures that successful CREATE and EDIT actions are added to the context.
    """
    from teddy_executor.core.domain.models import (
        ActionLog,
        ActionStatus,
        ExecutionReport,
        RunStatus,
        RunSummary,
    )
    from teddy_executor.core.domain.models.plan import ActionType
    from teddy_executor.core.ports.outbound.session_manager import ISessionManager
    from teddy_executor.core.ports.outbound.session_repository import ISessionRepository

    service = env.get_service(ISessionManager)
    repo = env.mock_port(ISessionRepository)
    repo.is_valid_path.return_value = True

    paths = {"existing.txt"}

    # 1. Successful CREATE
    create_log = ActionLog(
        status=ActionStatus.SUCCESS,
        action_type=ActionType.CREATE.value,
        params={"file_path": "new_file.py"},
    )

    # 2. Successful EDIT
    edit_log = ActionLog(
        status=ActionStatus.SUCCESS,
        action_type=ActionType.EDIT.value,
        params={"file_path": "edited_file.py"},
    )

    # 3. Failed CREATE (should NOT be added)
    failed_create_log = ActionLog(
        status=ActionStatus.FAILURE,
        action_type=ActionType.CREATE.value,
        params={"file_path": "failed_create.py"},
    )

    report = ExecutionReport(
        run_summary=RunSummary(
            status=RunStatus.SUCCESS, start_time=datetime.now(), end_time=datetime.now()
        ),
        action_logs=[create_log, edit_log, failed_create_log],
    )

    # Act
    # Access private method for unit test
    service._apply_execution_effects(paths, report)

    # Assert
    assert "new_file.py" in paths
    assert "edited_file.py" in paths
    assert "failed_create.py" not in paths
    assert "existing.txt" in paths


def test_create_session_deduplicates_context_paths(env):
    """
    Verify that create_session deduplicates overlapping paths in session.context,
    preserving insertion order (init.context first, then additional_context).
    """
    from datetime import datetime

    from teddy_executor.core.domain.models.session import SessionOptions
    from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
    from teddy_executor.core.ports.outbound.time_service import ITimeService

    # Arrange
    mock_time = env.mock_port(ITimeService)
    mock_prompts = env.mock_port(IPromptManager)
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()

    session_name = "dedup-test"
    agent_name = "pathfinder"
    # init.context has a duplicate path and overlapping additional_context
    # Order: path_a appears twice in init.context, path_b overlaps with additional_context
    mock_fs.read_file.side_effect = lambda p: {
        ".teddy/init.context": "path_a\npath_b\npath_a",
        f".teddy/prompts/{agent_name}.xml": "<prompt/>",
    }.get(p, "")
    mock_fs.path_exists.return_value = True
    mock_time.now.return_value = datetime(2026, 6, 8, 15, 0, 0)
    mock_time.now_utc.return_value = datetime(2026, 6, 8, 15, 0, 0)
    mock_prompts.get_prompt_content.side_effect = AssertionError(
        "create_session should not call get_prompt_content anymore"
    )

    # Act
    service.create_session(
        SessionOptions(
            name=session_name,
            agent_name=agent_name,
            additional_context=["path_b", "path_c"],
        )
    )

    # Assert: session.context should contain each path once, order preserved
    context_path = ".teddy/sessions/20260608_150000-dedup-test/session.context"
    context_call = mock_fs.find_call_by_path("write_file", context_path)
    written_content = context_call.args[1]
    lines = written_content.splitlines()

    # Expected: path_a (first occurrence preserved), path_b (from init.context, not additional_context), path_c
    assert lines == ["path_a", "path_b", "path_c"], (
        f"Expected deduped [path_a, path_b, path_c] but got {lines}"
    )


def test_get_cumulative_cost_returns_value_from_latest_meta(env):
    """
    Tests that get_cumulative_cost retrieves the cost from the latest turn's metadata.
    """
    # Arrange
    from teddy_executor.core.ports.outbound.session_repository import ISessionRepository

    repo = env.mock_port(ISessionRepository)
    service = env.get_service(ISessionManager)

    session_name = "my-session"
    latest_turn_path = ".teddy/sessions/my-session/02"
    repo.get_latest_turn.return_value = latest_turn_path
    repo.load_meta.return_value = {"cumulative_cost": 1.25}

    # Act
    cost = service.get_cumulative_cost(session_name)

    # Assert
    assert cost == 1.25
    repo.get_latest_turn.assert_called_once_with(session_name)
    repo.load_meta.assert_called_once_with(latest_turn_path)


def test_apply_execution_effects_uses_original_actions_when_action_logs_empty(env):
    """
    Regression test for Bug #16: When action_logs is empty (validation failure),
    the method should fall back to processing original_actions for CREATE/EDIT paths.
    """
    from teddy_executor.core.domain.models import (
        ExecutionReport,
        RunStatus,
        RunSummary,
    )
    from teddy_executor.core.domain.models.plan import ActionData, ActionType
    from teddy_executor.core.ports.outbound.session_repository import ISessionRepository

    service = env.get_service(ISessionManager)
    repo = env.mock_port(ISessionRepository)
    repo.is_valid_path.return_value = True

    paths = {"existing.txt"}

    # Create two original actions (CREAT + EDIT) that should be picked up
    create_action = ActionData(
        type=ActionType.CREATE.value,
        params={"file_path": "new_file_from_original.py"},
    )
    edit_action = ActionData(
        type=ActionType.EDIT.value,
        params={"file_path": "edited_file_from_original.py"},
    )

    # Build a validation-failure-style report: empty action_logs, populated original_actions
    report = ExecutionReport(
        run_summary=RunSummary(
            status=RunStatus.VALIDATION_FAILED,
            start_time=datetime.now(),
            end_time=datetime.now(),
            error="Plan validation failed.",
        ),
        original_actions=[create_action, edit_action],
        action_logs=[],
    )

    # Act
    service._apply_execution_effects(paths, report)

    # Assert – both paths from original_actions should be added
    assert "new_file_from_original.py" in paths
    assert "edited_file_from_original.py" in paths
    assert "existing.txt" in paths  # existing paths preserved


def test_apply_execution_effects_skips_original_actions_when_action_logs_present(env):
    """
    Regression test for Bug #16: When action_logs is NOT empty (normal execution),
    the original_actions fallback should NOT be used – only action_logs should be processed.
    """
    from teddy_executor.core.domain.models import (
        ActionLog,
        ActionStatus,
        ExecutionReport,
        RunStatus,
        RunSummary,
    )
    from teddy_executor.core.domain.models.plan import ActionData, ActionType
    from teddy_executor.core.ports.outbound.session_repository import ISessionRepository

    service = env.get_service(ISessionManager)
    repo = env.mock_port(ISessionRepository)
    repo.is_valid_path.return_value = True

    paths = {"existing.txt"}

    # Populate both action_logs and original_actions
    create_log = ActionLog(
        status=ActionStatus.SUCCESS,
        action_type=ActionType.CREATE.value,
        params={"file_path": "via_log.py"},
    )
    create_action = ActionData(
        type=ActionType.CREATE.value,
        params={"file_path": "via_original.py"},
    )

    report = ExecutionReport(
        run_summary=RunSummary(
            status=RunStatus.SUCCESS,
            start_time=datetime.now(),
            end_time=datetime.now(),
        ),
        original_actions=[create_action],
        action_logs=[create_log],
    )

    # Act
    service._apply_execution_effects(paths, report)

    # Assert – only from action_logs should be added (original_actions skipped)
    assert "via_log.py" in paths
    assert "via_original.py" not in paths, (
        "Original actions should not be processed when action_logs is non-empty"
    )
    assert "existing.txt" in paths


def test_create_session_reads_prompt_from_teddy_prompts(env):
    """
    Verifies that create_session reads prompt content from .teddy/prompts/<agent>.xml
    using IFileSystemManager, not via prompt_manager.get_prompt_content.
    """
    # Arrange
    from datetime import datetime

    from teddy_executor.core.domain.models.session import SessionOptions
    from teddy_executor.core.ports.outbound.time_service import ITimeService

    mock_time = env.mock_port(ITimeService)
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()

    session_name = "prompt-source"
    agent_name = "pathfinder"
    prompt_content = "<prompt>From .teddy/prompts/</prompt>"

    read_calls: list[str] = []

    def mock_read(path: str) -> str:
        read_calls.append(path)
        if path.endswith("init.context"):
            return "README.md"
        if path.endswith(f"prompts/{agent_name}.xml"):
            return prompt_content
        return ""

    mock_fs.read_file.side_effect = mock_read
    mock_fs.path_exists.return_value = True
    mock_time.now.return_value = datetime(2026, 6, 10, 16, 0, 0)
    mock_time.now_utc.return_value = datetime(2026, 6, 10, 16, 0, 0)

    # Do NOT mock prompt_manager.get_prompt_content — the new code should
    # read from filesystem instead.

    # Act
    service.create_session(SessionOptions(name=session_name, agent_name=agent_name))

    # Assert
    session_root = ".teddy/sessions/20260610_160000-prompt-source"
    expected_prompt_path = f"{session_root}/{agent_name}.xml"

    # Verify prompt was written to session root with content from .teddy/prompts/
    prompt_call = mock_fs.find_call_by_path("write_file", expected_prompt_path)
    assert prompt_call is not None, f"Expected write to {expected_prompt_path}"
    assert prompt_call.args[1] == prompt_content, (
        f"Expected content '{prompt_content}', got '{prompt_call.args[1]}'"
    )

    # Verify .teddy/prompts/pathfinder.xml was read
    teddy_prompt_read = any(
        f"prompts/{agent_name}.xml" in str(call)
        for call in mock_fs.read_file.call_args_list
    )
    assert teddy_prompt_read, (
        f"Expected read_file to be called with .teddy/prompts/{agent_name}.xml"
    )


# ---------------------------------------------------------------------------
# Agent validation error enrichment (Logic deliverable: create_session)
# ---------------------------------------------------------------------------


def test_create_session_raises_value_error_with_available_agents(env):
    """
    Verifies that create_session() includes available agents in the ValueError
    when the prompt file does not exist and agents are available.
    """
    # Arrange
    from datetime import datetime

    from teddy_executor.core.domain.models.session import SessionOptions
    from teddy_executor.core.ports.outbound.time_service import ITimeService
    from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
    from teddy_executor.core.ports.outbound.session_manager import ISessionManager

    mock_time = env.mock_port(ITimeService)
    mock_prompts = env.mock_port(IPromptManager)
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()

    session_name = "test-agent-err"
    agent_name = "nonexistent"

    # Mock init.context to exist, prompt path to not exist
    mock_fs.read_file.side_effect = lambda p: {
        ".teddy/init.context": "README.md",
        f".teddy/prompts/{agent_name}.xml": "UNUSED",
    }.get(p, "")
    mock_fs.path_exists.side_effect = lambda p: p == ".teddy/init.context"
    # Set the prompt_manager's get_available_agents (not mock_fs.list_directory)
    mock_prompts.get_available_agents.return_value = [
        "architect",
        "developer",
        "pathfinder",
    ]
    mock_time.now.return_value = datetime(2026, 6, 11, 10, 0, 0)
    mock_time.now_utc.return_value = datetime(2026, 6, 11, 10, 0, 0)

    # Act / Assert
    with pytest.raises(ValueError) as excinfo:
        service.create_session(SessionOptions(name=session_name, agent_name=agent_name))
    msg = str(excinfo.value)
    assert "Agent prompt 'nonexistent' not found" in msg
    assert "Available agents: architect, developer, pathfinder" in msg


def test_create_session_raises_value_error_without_agents(env):
    """
    Verifies that create_session() raises ValueError without the agents list
    when the prompt file does not exist and agents list is empty.
    """
    # Arrange
    from datetime import datetime

    from teddy_executor.core.domain.models.session import SessionOptions
    from teddy_executor.core.ports.outbound.time_service import ITimeService
    from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
    from teddy_executor.core.ports.outbound.session_manager import ISessionManager

    mock_time = env.mock_port(ITimeService)
    mock_prompts = env.mock_port(IPromptManager)
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()

    session_name = "test-no-agents"
    agent_name = "nonexistent"

    mock_fs.read_file.side_effect = lambda p: {
        ".teddy/init.context": "README.md",
    }.get(p, "")
    mock_fs.path_exists.side_effect = lambda p: p == ".teddy/init.context"
    # Empty agents list
    mock_prompts.get_available_agents.return_value = []
    mock_time.now.return_value = datetime(2026, 6, 11, 10, 0, 0)
    mock_time.now_utc.return_value = datetime(2026, 6, 11, 10, 0, 0)

    # Act / Assert
    with pytest.raises(ValueError) as excinfo:
        service.create_session(SessionOptions(name=session_name, agent_name=agent_name))
    msg = str(excinfo.value)
    assert "Agent prompt 'nonexistent' not found" in msg
    assert "Available agents:" not in msg, (
        "Should not include agent list when no agents available"
    )


def test_create_session_does_not_raise_when_prompt_exists(env):
    """
    Verifies that create_session() does not raise ValueError when the prompt file
    exists in .teddy/prompts/.
    """
    # Arrange
    from datetime import datetime

    from teddy_executor.core.domain.models.session import SessionOptions
    from teddy_executor.core.ports.outbound.time_service import ITimeService
    from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
    from teddy_executor.core.ports.outbound.session_manager import ISessionManager

    mock_time = env.mock_port(ITimeService)
    mock_prompts = env.mock_port(IPromptManager)  # noqa: F841
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()

    session_name = "test-valid-agent"
    agent_name = "architect"

    def mock_exists(path: str) -> bool:
        if path == ".teddy/init.context":
            return True
        if path.endswith(f"prompts/{agent_name}.xml"):
            return True
        return False

    mock_fs.path_exists.side_effect = mock_exists
    mock_fs.read_file.side_effect = lambda p: {
        ".teddy/init.context": "README.md",
        f".teddy/prompts/{agent_name}.xml": "<prompt/>",
    }.get(p, "")
    mock_time.now.return_value = datetime(2026, 6, 11, 10, 0, 0)
    mock_time.now_utc.return_value = datetime(2026, 6, 11, 10, 0, 0)
    # Note: create_session requires create_turn_directory and other write operations
    # We'll mock write_file to accept any call (no side effect needed)
    mock_fs.write_file.side_effect = None  # allow any write

    # Act & Assert: should not raise
    result = service.create_session(
        SessionOptions(name=session_name, agent_name=agent_name)
    )
    assert result is not None  # session root returned
    assert session_name in result  # session root contains the session name
