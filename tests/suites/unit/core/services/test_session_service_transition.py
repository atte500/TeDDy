import yaml
from datetime import datetime, timezone
from pathlib import Path
from teddy_executor.core.domain.models.execution_report import (
    ExecutionReport,
    RunSummary,
    RunStatus,
)
from teddy_executor.core.domain.models.plan import ActionData, ActionType
from teddy_executor.core.ports.outbound.session_manager import ISessionManager


def setup_transition_harness(env, meta_id="abc", context="file_a.py"):
    """Helper to setup a standardized transition mock state."""
    mock_fs = env.get_mock_filesystem()
    plan_path = ".teddy/sessions/feat-x/01/plan.md"
    current_meta = {"turn_id": meta_id, "agent_name": "pathfinder"}
    current_prompt = "system prompt content"

    valid_paths = {
        ".teddy/sessions/feat-x/01/meta.yaml",
        ".teddy/sessions/feat-x/01/pathfinder.xml",
        ".teddy/sessions/feat-x/01/turn.context",
    }
    mock_fs.path_exists.side_effect = lambda p: p in valid_paths
    mock_fs.read_file.side_effect = lambda path: {
        ".teddy/sessions/feat-x/01/meta.yaml": yaml.dump(current_meta),
        ".teddy/sessions/feat-x/01/pathfinder.xml": current_prompt,
        ".teddy/sessions/feat-x/01/turn.context": context,
    }.get(path, "")
    return plan_path


def test_transition_to_next_turn_creates_directory_and_linkage(env):
    """
    transition_to_next_turn should create a new turn directory (T_next)
    and seed it with metadata linked to the current turn (T_current).
    """
    # Arrange
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()
    plan_path = setup_transition_harness(env)

    now = datetime.now(timezone.utc)
    report = ExecutionReport(
        run_summary=RunSummary(status=RunStatus.SUCCESS, start_time=now, end_time=now),
        original_actions=[],
    )

    # Act
    next_turn_path = service.transition_to_next_turn(plan_path, report)

    # Assert
    assert next_turn_path == ".teddy/sessions/feat-x/02"
    mock_fs.create_directory.assert_any_call(str(Path(".teddy/sessions/feat-x/02")))

    # Verify meta.yaml linkage
    meta_call = next(
        c for c in mock_fs.write_file.call_args_list if "02/meta.yaml" in c.args[0]
    )
    meta_data = yaml.safe_load(meta_call.args[1])
    assert meta_data["parent_turn_id"] == "abc"

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


def test_transition_to_next_turn_applies_read_side_effects(env):
    """
    transition_to_next_turn should add READ resources to the next turn's context.
    """
    # Arrange
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()
    plan_path = setup_transition_harness(env, context="file_a.py")

    action_read = ActionData(
        type=ActionType.READ.value, params={"Resource": "[new_file.py](/new_file.py)"}
    )

    from teddy_executor.core.domain.models import ActionLog, ActionStatus

    now = datetime.now(timezone.utc)
    report = ExecutionReport(
        run_summary=RunSummary(status=RunStatus.SUCCESS, start_time=now, end_time=now),
        original_actions=[action_read],
        action_logs=[
            ActionLog(
                status=ActionStatus.SUCCESS,
                action_type=ActionType.READ.value,
                params=action_read.params,
            ),
        ],
    )

    # Act
    service.transition_to_next_turn(plan_path, report)

    # Assert
    context_call = next(
        c for c in mock_fs.write_file.call_args_list if "02/turn.context" in c.args[0]
    )
    next_context = context_call.args[1]

    assert "file_a.py" in next_context  # Persisted
    assert "new_file.py" in next_context  # Added
    assert "01/report.md" in next_context  # Always added


def test_transition_to_next_turn_appends_plan_and_report_on_validation_failure(env):
    """
    transition_to_next_turn should append BOTH plan.md and report.md
    even if the execution failed validation.
    """
    # Arrange
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()
    plan_path = setup_transition_harness(env, meta_id="01", context="existing.py")

    # Act
    service.transition_to_next_turn(plan_path, execution_report=None)

    # Assert
    context_call = next(
        c for c in mock_fs.write_file.call_args_list if "02/turn.context" in c.args[0]
    )
    next_context = context_call.args[1]

    assert "01/plan.md" in next_context
    assert "01/report.md" in next_context
    assert "01/plan.md" in next_context
    assert "01/report.md" in next_context


def test_transition_to_next_turn_propagates_replan_and_user_request_on_validation_failure(
    env,
):
    """
    On validation failure, transition_to_next_turn should set is_replan: True
    and carry forward the parent's user_request into the next turn's metadata.
    """
    # Arrange
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()
    plan_path = ".teddy/sessions/feat-x/01/plan.md"
    current_meta = {
        "turn_id": "01",
        "agent_name": "pathfinder",
        "user_request": "Implement feature X",
    }
    current_prompt = "system prompt content"

    valid_paths = {
        ".teddy/sessions/feat-x/01/meta.yaml",
        ".teddy/sessions/feat-x/01/pathfinder.xml",
        ".teddy/sessions/feat-x/01/turn.context",
    }
    mock_fs.path_exists.side_effect = lambda p: p in valid_paths
    mock_fs.read_file.side_effect = lambda path: {
        ".teddy/sessions/feat-x/01/meta.yaml": yaml.dump(current_meta),
        ".teddy/sessions/feat-x/01/pathfinder.xml": current_prompt,
        ".teddy/sessions/feat-x/01/turn.context": "existing.py",
    }.get(path, "")

    # Act
    service.transition_to_next_turn(
        plan_path, execution_report=None, is_validation_failure=True
    )

    # Assert
    meta_call = next(
        c for c in mock_fs.write_file.call_args_list if "02/meta.yaml" in c.args[0]
    )
    meta_data = yaml.safe_load(meta_call.args[1])
    assert meta_data.get("is_replan") is True
    assert meta_data.get("user_request") == "Implement feature X"


def test_transition_to_next_turn_handles_no_parent_user_request(env):
    """
    If there is no user_request in the parent's metadata, the next turn's metadata
    should not contain user_request even if is_validation_failure is True.
    """
    # Arrange
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()
    plan_path = ".teddy/sessions/feat-x/01/plan.md"
    current_meta = {
        "turn_id": "01",
        "agent_name": "pathfinder",
        # no user_request field
    }
    current_prompt = "system prompt content"

    valid_paths = {
        ".teddy/sessions/feat-x/01/meta.yaml",
        ".teddy/sessions/feat-x/01/pathfinder.xml",
        ".teddy/sessions/feat-x/01/turn.context",
    }
    mock_fs.path_exists.side_effect = lambda p: p in valid_paths
    mock_fs.read_file.side_effect = lambda path: {
        ".teddy/sessions/feat-x/01/meta.yaml": yaml.dump(current_meta),
        ".teddy/sessions/feat-x/01/pathfinder.xml": current_prompt,
        ".teddy/sessions/feat-x/01/turn.context": "existing.py",
    }.get(path, "")

    # Act
    service.transition_to_next_turn(
        plan_path, execution_report=None, is_validation_failure=True
    )

    # Assert
    meta_call = next(
        c for c in mock_fs.write_file.call_args_list if "02/meta.yaml" in c.args[0]
    )
    meta_data = yaml.safe_load(meta_call.args[1])
    assert meta_data.get("is_replan") is True
    assert "user_request" not in meta_data
