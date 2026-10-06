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
    mock_fs.list_directory.side_effect = lambda d: {
        ".teddy/prompts": [f"{agent_name}.xml"],
    }.get(d, [])
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
    mock_fs.list_directory.side_effect = lambda d: {
        ".teddy/prompts": [f"{agent_name}.xml"],
    }.get(d, [])
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
    mock_fs.list_directory.side_effect = lambda d: {
        ".teddy/prompts": [f"{agent_name}.xml"],
    }.get(d, [])
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
    mock_fs.list_directory.side_effect = lambda d: {
        ".teddy/prompts": [f"{agent_name}.xml"],
    }.get(d, [])
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
    mock_fs.list_directory.side_effect = lambda d: {
        ".teddy/prompts": [f"{agent_name}.xml"],
    }.get(d, [])
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
        if path == ".teddy/prompts":
            return True
        if path.endswith(f"prompts/{agent_name}.xml"):
            return True
        return False

    mock_fs.path_exists.side_effect = mock_exists
    mock_fs.list_directory.side_effect = lambda d: {
        ".teddy/prompts": [f"{agent_name}.xml"],
    }.get(d, [])
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


def test_claim_session_root_claims_base_name_when_free(env):
    """_claim_session_root claims the base name when the root is free."""
    # Arrange
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()
    mock_fs.create_directory_exclusive.return_value = True

    # Act
    result = service._claim_session_root("20260417_120000-feat-x")

    # Assert
    assert result == ".teddy/sessions/20260417_120000-feat-x"
    assert mock_fs.create_directory_exclusive.call_count == 1
    mock_fs.find_call_by_path(
        "create_directory_exclusive", ".teddy/sessions/20260417_120000-feat-x"
    )


def test_claim_session_root_retries_with_suffix_when_occupied(env):
    """Occupied base root forces a -2 suffix retry."""
    # Arrange
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()
    mock_fs.create_directory_exclusive.side_effect = lambda p: {
        ".teddy/sessions/20260417_120000-feat-x-2": True,
    }.get(p, False)

    # Act
    result = service._claim_session_root("20260417_120000-feat-x")

    # Assert
    assert result == ".teddy/sessions/20260417_120000-feat-x-2"
    mock_fs.find_call_by_path(
        "create_directory_exclusive", ".teddy/sessions/20260417_120000-feat-x"
    )
    mock_fs.find_call_by_path(
        "create_directory_exclusive", ".teddy/sessions/20260417_120000-feat-x-2"
    )


def test_claim_session_root_stops_at_first_success(env):
    """The retry loop stops incrementing as soon as a claim succeeds."""
    # Arrange
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()
    mock_fs.create_directory_exclusive.side_effect = lambda p: p.endswith("-3")

    # Act
    result = service._claim_session_root("20260417_120000-feat-x")

    # Assert
    assert result == ".teddy/sessions/20260417_120000-feat-x-3"
    assert mock_fs.create_directory_exclusive.call_count == 3


def test_create_session_claims_distinct_root_when_base_occupied(env):
    """A collision on the base root forces create_session to claim the -2 root."""
    # Arrange
    mock_time = env.mock_port(ITimeService)
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()

    mock_time.now.return_value = datetime(2026, 4, 17, 12, 0, 0)
    mock_time.now_utc.return_value = datetime(2026, 4, 17, 12, 0, 0)
    mock_fs.read_file.side_effect = lambda p: {
        ".teddy/init.context": "README.md",
        ".teddy/prompts/pathfinder.xml": "<prompt/>",
    }.get(p, "")
    mock_fs.path_exists.return_value = True
    mock_fs.list_directory.side_effect = lambda d: {
        ".teddy/prompts": ["pathfinder.xml"],
    }.get(d, [])
    # Occupy the base root; every other candidate (e.g., -2) is free.
    mock_fs.create_directory_exclusive.side_effect = lambda p: (
        not p.endswith(".teddy/sessions/20260417_120000-feat-x")
    )

    # Act
    service.create_session(SessionOptions(name="feat-x", agent_name="pathfinder"))

    # Assert: the base name was attempted, then -2 was claimed
    mock_fs.find_call_by_path(
        "create_directory_exclusive", ".teddy/sessions/20260417_120000-feat-x"
    )
    mock_fs.find_call_by_path(
        "create_directory_exclusive", ".teddy/sessions/20260417_120000-feat-x-2"
    )
    # Session artifacts land under the -2 root
    mock_fs.find_call_by_path(
        "write_file", ".teddy/sessions/20260417_120000-feat-x-2/session.context"
    )
    mock_fs.find_call_by_path(
        "write_file", ".teddy/sessions/20260417_120000-feat-x-2/pathfinder.xml"
    )
    mock_fs.find_call_by_path(
        "write_file", ".teddy/sessions/20260417_120000-feat-x-2/01/meta.yaml"
    )


def test_create_session_collision_leaves_first_session_untouched(env):
    """The first session's ledger files are never written by the colliding creator."""
    # Arrange
    mock_time = env.mock_port(ITimeService)
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()

    mock_time.now.return_value = datetime(2026, 4, 17, 12, 0, 0)
    mock_time.now_utc.return_value = datetime(2026, 4, 17, 12, 0, 0)
    mock_fs.read_file.side_effect = lambda p: {
        ".teddy/init.context": "README.md",
        ".teddy/prompts/pathfinder.xml": "<prompt/>",
    }.get(p, "")
    mock_fs.path_exists.return_value = True
    mock_fs.list_directory.side_effect = lambda d: {
        ".teddy/prompts": ["pathfinder.xml"],
    }.get(d, [])
    mock_fs.create_directory_exclusive.side_effect = lambda p: (
        not p.endswith(".teddy/sessions/20260417_120000-feat-x")
    )

    # Act
    service.create_session(SessionOptions(name="feat-x", agent_name="pathfinder"))

    # Assert: no write touches the base (first session's) root
    base_root = ".teddy/sessions/20260417_120000-feat-x"
    with pytest.raises(AssertionError):
        mock_fs.find_call_by_path("write_file", f"{base_root}/session.context")
    with pytest.raises(AssertionError):
        mock_fs.find_call_by_path("write_file", f"{base_root}/pathfinder.xml")
    with pytest.raises(AssertionError):
        mock_fs.find_call_by_path("write_file", f"{base_root}/01/meta.yaml")


def test_claim_session_root_retries_via_continuation_name_when_digit_suffix_occupied(
    env,
):
    """An occupied digit-suffixed base retries via the continuation chain (-N+1), not a fresh -2 suffix."""
    # Arrange
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()

    # Occupy the digit-suffixed base; every other candidate (including -3) is free.
    mock_fs.create_directory_exclusive.side_effect = lambda p: (
        not p.endswith("20260417_120000-feat-x-2")
    )

    # Act
    result = service._claim_session_root("20260417_120000-feat-x-2")

    # Assert: the chain walked base -> -3 via the continuation convention
    assert result == ".teddy/sessions/20260417_120000-feat-x-3"
    mock_fs.find_call_by_path(
        "create_directory_exclusive", ".teddy/sessions/20260417_120000-feat-x-2"
    )
    mock_fs.find_call_by_path(
        "create_directory_exclusive", ".teddy/sessions/20260417_120000-feat-x-3"
    )
    # The legacy fresh-suffix candidate (base-2-2) must never fire
    with pytest.raises(AssertionError):
        mock_fs.find_call_by_path(
            "create_directory_exclusive", ".teddy/sessions/20260417_120000-feat-x-2-2"
        )


def test_claim_session_root_continuation_chain_walks_multiple_hops(env):
    """The retry chain keeps incrementing through the continuation convention until a free root is claimed."""
    # Arrange
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()

    # First two candidates occupied, third wins (ordinal outcomes so the
    # loop terminates under both the legacy and generalized behaviors).
    outcomes = [False, False, True]
    mock_fs.create_directory_exclusive.side_effect = lambda p: outcomes.pop(0)

    # Act
    result = service._claim_session_root("20260417_120000-foo-2")

    # Assert: the chain walked -2 -> -3 -> -4
    assert result == ".teddy/sessions/20260417_120000-foo-4"
    assert mock_fs.create_directory_exclusive.call_count == 3
    mock_fs.find_call_by_path(
        "create_directory_exclusive", ".teddy/sessions/20260417_120000-foo-3"
    )
    mock_fs.find_call_by_path(
        "create_directory_exclusive", ".teddy/sessions/20260417_120000-foo-4"
    )


# ---------------------------------------------------------------------------
# Seam deliverable: set_session_agent
# ---------------------------------------------------------------------------


def test_set_session_agent_updates_meta_yaml_and_copies_prompt(env):
    """
    Verifies that set_session_agent updates meta.yaml with the new agent_name,
    copies the new prompt to the session root.
    """
    # Arrange
    from teddy_executor.core.ports.outbound.session_repository import ISessionRepository

    repo = env.mock_port(ISessionRepository)
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()

    session_name = "test-session"
    session_root = f".teddy/sessions/{session_name}"
    latest_turn_path = f"{session_root}/03"

    # Existing meta.yaml has agent "pathfinder"
    existing_meta = {"agent_name": "pathfinder", "turn_id": "03"}
    repo.get_latest_turn.return_value = latest_turn_path
    repo.load_meta.return_value = existing_meta
    repo.to_root_relative.return_value = "test.xml"

    # Stale prompt file exists at session root
    old_prompt_stem = "pathfinder.xml"

    # .teddy/prompts/ contains Developer.xml (case-insensitive match)
    mock_fs.path_exists.side_effect = lambda p: (
        p
        in {
            ".teddy/prompts",
            ".teddy/prompts/Developer.xml",
        }
    )
    mock_fs.list_directory.side_effect = lambda d: {
        ".teddy/prompts": ["architect.xml", "Developer.xml"],
        session_root: [old_prompt_stem, "turn.context"],
    }.get(d, [])
    mock_fs.read_file.side_effect = lambda p: {
        ".teddy/prompts/Developer.xml": "<prompt>developer content</prompt>",
    }.get(p, "")

    # Act
    service.set_session_agent(session_name, "developer")

    # Assert
    # 1. meta.yaml was updated with new agent_name
    repo.save_meta.assert_called_once_with(
        f"{latest_turn_path}/meta.yaml",
        {"agent_name": "developer", "turn_id": "03"},
    )

    # 2. New prompt was written to session root
    mock_fs.write_file.assert_any_call(
        f"{session_root}/Developer.xml",
        "<prompt>developer content</prompt>",
    )


def test_set_session_agent_removes_stale_prompt_files(env):
    """
    Verifies that set_session_agent removes stale prompt files with different stems.
    """
    # Arrange
    from teddy_executor.core.ports.outbound.session_repository import ISessionRepository

    repo = env.mock_port(ISessionRepository)
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()

    session_name = "test-stale"
    session_root = f".teddy/sessions/{session_name}"
    latest_turn_path = f"{session_root}/03"

    existing_meta = {"agent_name": "pathfinder", "turn_id": "03"}
    repo.get_latest_turn.return_value = latest_turn_path
    repo.load_meta.return_value = existing_meta
    repo.to_root_relative.return_value = "test.xml"

    # Session root has: pathfinder.xml (current), assistant.xml (stale from previous switch), turn.context
    session_files = ["pathfinder.xml", "assistant.xml", "turn.context"]
    mock_fs.path_exists.side_effect = lambda p: (
        p
        in {
            ".teddy/prompts",
            ".teddy/prompts/Developer.xml",
        }
    )
    mock_fs.list_directory.side_effect = lambda d: {
        ".teddy/prompts": [
            "architect.xml",
            "Developer.xml",
            "assistant.xml",
            "pathfinder.xml",
        ],
        session_root: session_files,
    }.get(d, [])
    mock_fs.read_file.side_effect = lambda p: {
        ".teddy/prompts/Developer.xml": "<prompt>developer content</prompt>",
    }.get(p, "")

    # Act
    service.set_session_agent(session_name, "developer")

    # Assert
    # 1. New prompt written
    mock_fs.write_file.assert_any_call(
        f"{session_root}/Developer.xml",
        "<prompt>developer content</prompt>",
    )

    # 2. Stale prompt files removed (pathfinder.xml and assistant.xml),
    #    but turn.context is NOT removed
    mock_fs.remove_file.assert_any_call(f"{session_root}/pathfinder.xml")
    mock_fs.remove_file.assert_any_call(f"{session_root}/assistant.xml")

    # 3. turn.context should NOT have been removed
    remove_calls = [call.args[0] for call in mock_fs.remove_file.call_args_list]
    assert f"{session_root}/turn.context" not in remove_calls, (
        "Non-prompt files should not be removed"
    )


def test_create_session_does_not_write_provider_to_initial_meta(env):
    """Verify that create_session does NOT write the 'provider' option to initial meta_data.

    The 'provider' override path was removed; only the display path (from
    _hidden_params) may populate meta["provider"] later via update_meta.
    """
    from teddy_executor.core.domain.models.session import SessionOptions

    mock_time = env.mock_port(ITimeService)
    mock_prompts = env.mock_port(IPromptManager)
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()

    session_name = "provider-absent-session"
    agent_name = "pathfinder"
    init_context = "README.md"
    agent_prompt = "<prompt>Pathfinder content</prompt>"

    mock_fs.read_file.side_effect = lambda p: {
        ".teddy/init.context": init_context,
        f".teddy/prompts/{agent_name}.xml": agent_prompt,
    }.get(p, "")
    mock_fs.path_exists.return_value = True
    mock_fs.list_directory.side_effect = lambda d: {
        ".teddy/prompts": [f"{agent_name}.xml"],
    }.get(d, [])
    mock_time.now.return_value = datetime(2026, 10, 6, 12, 0, 0)
    mock_time.now_utc.return_value = datetime(2026, 10, 6, 12, 0, 0)
    mock_prompts.get_prompt_content.side_effect = AssertionError(
        "create_session should not call get_prompt_content anymore"
    )

    # Create session with a provider option (simulating old CLI override)
    service.create_session(
        SessionOptions(
            name=session_name,
            agent_name=agent_name,
            provider="baseten",
        )
    )

    # Inspect the meta_data written to disk. The mock filesystem stores files;
    # we need to capture the meta.yaml content. Since the service writes meta.yaml
    # via IFileSystemManager.write_file, we can check that call.
    yaml_call = None
    for call_args in mock_fs.write_file.call_args_list:
        # write_file(path, content) – we look for calls containing "meta.yaml"
        if "meta.yaml" in call_args[0][0]:
            yaml_call = call_args
            break

    assert yaml_call is not None, "No meta.yaml write found"
    content = yaml_call[0][1]
    # provider should NOT be in the meta content
    assert "provider" not in content, (
        f"Unexpected 'provider' key found in initial meta.yaml:\n{content}"
    )
