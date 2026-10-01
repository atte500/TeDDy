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
        ".teddy/sessions/feat-x/pathfinder.xml",
        ".teddy/sessions/feat-x/01/turn.context",
    }
    mock_fs.path_exists.side_effect = lambda p: p in valid_paths
    mock_fs.read_file.side_effect = lambda path: {
        ".teddy/sessions/feat-x/01/meta.yaml": yaml.dump(current_meta),
        ".teddy/sessions/feat-x/pathfinder.xml": current_prompt,
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

    # Prompt is no longer copied to turn directories
    assert not any(
        "02/pathfinder.xml" in c.args[0] for c in mock_fs.write_file.call_args_list
    )

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
        ".teddy/sessions/feat-x/pathfinder.xml",
        ".teddy/sessions/feat-x/01/turn.context",
    }
    mock_fs.path_exists.side_effect = lambda p: p in valid_paths
    mock_fs.read_file.side_effect = lambda path: {
        ".teddy/sessions/feat-x/01/meta.yaml": yaml.dump(current_meta),
        ".teddy/sessions/feat-x/pathfinder.xml": current_prompt,
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
        ".teddy/sessions/feat-x/pathfinder.xml",
        ".teddy/sessions/feat-x/01/turn.context",
    }
    mock_fs.path_exists.side_effect = lambda p: p in valid_paths
    mock_fs.read_file.side_effect = lambda path: {
        ".teddy/sessions/feat-x/01/meta.yaml": yaml.dump(current_meta),
        ".teddy/sessions/feat-x/pathfinder.xml": current_prompt,
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


def setup_migration_harness(env):
    """Arrangement for turn-99 migration transition tests (continuation root feat-x-2)."""
    mock_fs = env.get_mock_filesystem()
    plan_path = ".teddy/sessions/feat-x/99/plan.md"
    valid_paths = {
        ".teddy/sessions/feat-x/99/meta.yaml",
        ".teddy/sessions/feat-x/pathfinder.xml",
        ".teddy/sessions/feat-x/99/turn.context",
        ".teddy/sessions/feat-x/session.context",
    }
    mock_fs.path_exists.side_effect = lambda p: p in valid_paths
    mock_fs.read_file.side_effect = lambda path: {
        ".teddy/sessions/feat-x/99/meta.yaml": yaml.dump(
            {"turn_id": "99", "agent_name": "pathfinder"}
        ),
        ".teddy/sessions/feat-x/pathfinder.xml": "system prompt content",
        ".teddy/sessions/feat-x/99/turn.context": "file_a.py",
        ".teddy/sessions/feat-x/session.context": "ctx.md",
    }.get(path, "")
    return plan_path


def test_migration_claims_continuation_root_when_occupied(env):
    """Turn-99 migration must exclusive-claim the continuation root; an occupied
    root retries to -N+1 and ALL persistence lands on the claimed root."""
    # Arrange
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()
    plan_path = setup_migration_harness(env)

    # Occupy the continuation root (sibling session feat-x-2 exists); -3 is free.
    mock_fs.create_directory_exclusive.side_effect = lambda p: (
        not p.endswith(".teddy/sessions/feat-x-2")
    )

    # Act
    result = service.transition_to_next_turn(plan_path)

    # Assert: migration claimed the next free continuation root and used it
    # for the returned turn directory and all persistence.
    assert result == ".teddy/sessions/feat-x-3/01"
    mock_fs.find_call_by_path("create_directory_exclusive", ".teddy/sessions/feat-x-2")
    mock_fs.find_call_by_path("create_directory_exclusive", ".teddy/sessions/feat-x-3")
    mock_fs.find_call_by_path("create_directory", ".teddy/sessions/feat-x-3/01")

    # The occupied sibling's tree must remain untouched.
    for c in mock_fs.mock_calls:
        name = c[0].split(".")[-1]
        if (
            name in ("write_file", "create_file", "create_directory", "edit_file")
            and c.args
            and isinstance(c.args[0], str)
        ):
            path = c.args[0].replace("\\", "/")
            assert "sessions/feat-x-2/" not in path, (
                f"Sibling session polluted via {name}: {path}"
            )


def test_migration_claims_root_before_persistence(env):
    """The migration path must exclusive-claim the continuation root BEFORE any
    persistence (create_turn_directory / writes) targets the claimed tree."""
    # Arrange
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()
    plan_path = setup_migration_harness(env)

    # Act (root is free: harness happy-path default returns True)
    result = service.transition_to_next_turn(plan_path)

    # Assert
    assert result == ".teddy/sessions/feat-x-2/01"
    mock_fs.find_call_by_path("create_directory_exclusive", ".teddy/sessions/feat-x-2")
    order = [c[0].split(".")[-1] for c in mock_fs.mock_calls]
    claim_index = order.index("create_directory_exclusive")
    first_persistence_index = next(
        i for i, name in enumerate(order) if name in ("create_directory", "write_file")
    )
    assert claim_index < first_persistence_index
