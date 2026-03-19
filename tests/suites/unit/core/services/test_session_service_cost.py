import yaml
from datetime import datetime, timezone
from teddy_executor.core.domain.models.execution_report import (
    ExecutionReport,
    RunSummary,
    RunStatus,
)
from teddy_executor.core.ports.outbound.session_manager import ISessionManager


def test_transition_to_next_turn_updates_cumulative_cost(env):
    """
    Verify that cumulative cost is correctly carried forward and incremented.
    """
    # Arrange
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()

    plan_path = ".teddy/sessions/feat-x/01/plan.md"
    current_meta = {"turn_id": "01", "cumulative_cost": 1.50}

    valid_paths = {
        ".teddy/sessions/feat-x/01/meta.yaml",
        ".teddy/sessions/feat-x/01/pathfinder.xml",
        ".teddy/sessions/feat-x/01/turn.context",
    }
    mock_fs.path_exists.side_effect = lambda p: p in valid_paths
    mock_fs.read_file.side_effect = lambda path: {
        ".teddy/sessions/feat-x/01/meta.yaml": yaml.dump(current_meta),
        ".teddy/sessions/feat-x/01/pathfinder.xml": "<prompt/>",
        ".teddy/sessions/feat-x/01/turn.context": "file.py",
    }.get(path, "")

    now = datetime.now(timezone.utc)
    report = ExecutionReport(
        run_summary=RunSummary(status=RunStatus.SUCCESS, start_time=now, end_time=now),
        original_actions=[],
    )

    # Act
    service.transition_to_next_turn(plan_path, report, turn_cost=0.75)

    # Assert
    meta_call = next(
        c for c in mock_fs.write_file.call_args_list if "02/meta.yaml" in c.args[0]
    )
    meta_data = yaml.safe_load(meta_call.args[1])
    expected_cost = 2.25
    assert meta_data["cumulative_cost"] == expected_cost
