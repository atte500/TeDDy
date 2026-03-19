import yaml
from datetime import datetime, timezone
from teddy_executor.core.domain.models.execution_report import (
    ExecutionReport,
    RunSummary,
    RunStatus,
)
from teddy_executor.core.domain.models.plan import ActionData, ActionType
from teddy_executor.core.ports.outbound.session_manager import ISessionManager


def test_transition_to_next_turn_creates_directory_and_linkage(env):
    """
    transition_to_next_turn should create a new turn directory (T_next)
    and seed it with metadata linked to the current turn (T_current).
    """
    # Arrange
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()

    # Mock current turn state
    plan_path = ".teddy/sessions/feat-x/01/plan.md"
    current_meta = {"turn_id": "abc", "agent_name": "pathfinder"}
    current_prompt = "system prompt content"
    current_context = "file_a.py"

    # Mocking FS for T_current
    valid_paths = {
        ".teddy/sessions/feat-x/01/meta.yaml",
        ".teddy/sessions/feat-x/01/pathfinder.xml",
        ".teddy/sessions/feat-x/01/turn.context",
    }
    mock_fs.path_exists.side_effect = lambda p: p in valid_paths
    mock_fs.read_file.side_effect = lambda path: {
        ".teddy/sessions/feat-x/01/meta.yaml": yaml.dump(current_meta),
        ".teddy/sessions/feat-x/01/pathfinder.xml": current_prompt,
        ".teddy/sessions/feat-x/01/turn.context": current_context,
    }.get(path, "")

    now = datetime.now(timezone.utc)
    # Use a real report
    report = ExecutionReport(
        run_summary=RunSummary(status=RunStatus.SUCCESS, start_time=now, end_time=now),
        original_actions=[],
    )

    # Act
    next_turn_path = service.transition_to_next_turn(plan_path, report)

    # Assert
    assert next_turn_path == ".teddy/sessions/feat-x/02"

    # Verify directory creation
    mock_fs.create_directory.assert_any_call(".teddy/sessions/feat-x/02")

    # Verify meta.yaml linkage
    meta_call = next(
        c for c in mock_fs.write_file.call_args_list if "02/meta.yaml" in c.args[0]
    )
    meta_data = yaml.safe_load(meta_call.args[1])
    assert meta_data["parent_turn_id"] == "abc"
    assert meta_data["turn_id"] == "02"

    # Verify pathfinder.xml is copied
    prompt_call = next(
        c for c in mock_fs.write_file.call_args_list if "02/pathfinder.xml" in c.args[0]
    )
    assert prompt_call.args[1] == "system prompt content"

    # Verify report.md is added to context
    context_call = next(
        c for c in mock_fs.write_file.call_args_list if "02/turn.context" in c.args[0]
    )
    assert "01/report.md" in context_call.args[1]


def test_transition_to_next_turn_applies_read_and_prune_side_effects(env):
    """
    transition_to_next_turn should add READ resources to and remove PRUNE
    resources from the next turn's context.
    """
    # Arrange
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()

    plan_path = ".teddy/sessions/feat-x/01/plan.md"
    current_meta = {"turn_id": "abc"}
    current_prompt = "system prompt content"
    current_context = "file_a.py\nfile_b.py"  # file_b.py is in context

    valid_paths = {
        ".teddy/sessions/feat-x/01/meta.yaml",
        ".teddy/sessions/feat-x/01/pathfinder.xml",
        ".teddy/sessions/feat-x/01/turn.context",
    }
    mock_fs.path_exists.side_effect = lambda p: p in valid_paths
    mock_fs.read_file.side_effect = lambda path: {
        ".teddy/sessions/feat-x/01/meta.yaml": yaml.dump(current_meta),
        ".teddy/sessions/feat-x/01/pathfinder.xml": current_prompt,
        ".teddy/sessions/feat-x/01/turn.context": current_context,
    }.get(path, "")

    # Mock Report with real ActionData objects
    action_read = ActionData(
        type=ActionType.READ.value, params={"Resource": "[new_file.py](/new_file.py)"}
    )
    action_prune = ActionData(
        type=ActionType.PRUNE.value, params={"Resource": "[file_b.py](/file_b.py)"}
    )

    now = datetime.now(timezone.utc)
    report = ExecutionReport(
        run_summary=RunSummary(status=RunStatus.SUCCESS, start_time=now, end_time=now),
        original_actions=[action_read, action_prune],
    )

    # Act
    service.transition_to_next_turn(plan_path, report)

    # Assert
    context_call = next(
        c for c in mock_fs.write_file.call_args_list if "02/turn.context" in c.args[0]
    )
    next_context = context_call.args[1]

    assert "file_a.py" in next_context  # Persisted from T_current
    assert "new_file.py" in next_context  # Added via READ
    assert "01/report.md" in next_context  # Always added
    assert "file_b.py" not in next_context  # Removed via PRUNE
