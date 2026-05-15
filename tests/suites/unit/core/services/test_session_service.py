from datetime import datetime
from pathlib import Path
from unittest.mock import ANY

from teddy_executor.core.ports.outbound.session_manager import ISessionManager
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

    mock_fs.read_file.return_value = init_context
    mock_time.now.return_value = datetime(2026, 4, 17, 12, 0, 0)
    # Mock UTC time for metadata
    mock_time.now_utc.return_value = datetime(2026, 4, 17, 12, 0, 0)
    mock_prompts.get_prompt_content.return_value = agent_prompt

    # Act
    service.create_session(name=session_name, agent_name=agent_name)

    # Assert
    # 1. Directory creation
    mock_fs.create_directory.assert_any_call(
        str(Path(".teddy/sessions/20260417_120000-feat-x/01"))
    )

    # 2. session.context creation (with comments stripped)
    mock_fs.write_file.assert_any_call(
        str(Path(".teddy/sessions/20260417_120000-feat-x/session.context")),
        clean_context,
    )

    # 3. pathfinder.xml creation
    mock_fs.write_file.assert_any_call(
        str(Path(".teddy/sessions/20260417_120000-feat-x/01/pathfinder.xml")),
        agent_prompt,
    )

    # 4. meta.yaml creation
    mock_fs.write_file.assert_any_call(
        str(Path(".teddy/sessions/20260417_120000-feat-x/01/meta.yaml")), ANY
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
    mock_prompts.get_prompt_content.return_value = "<prompt/>"
    mock_fs.read_file.return_value = "README.md"

    # Act
    service.create_session(
        name=session_name, agent_name=agent_name, initial_request=initial_request
    )

    # Assert
    expected_path = str(
        Path(".teddy/sessions/20260515_100000-goal-x/initial_request.md")
    )
    mock_fs.write_file.assert_any_call(expected_path, initial_request)


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
