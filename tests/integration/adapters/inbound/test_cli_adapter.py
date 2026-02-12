from pathlib import Path
from unittest.mock import MagicMock, patch
from typer.testing import CliRunner

from tests.acceptance.plan_builder import MarkdownPlanBuilder

from teddy_executor.core.domain.models import (
    ExecutionReport,
    RunSummary,
    RunStatus,
)
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator
from teddy_executor.main import app

runner = CliRunner()


@patch("teddy_executor.main.ExecutionOrchestrator")
def test_cli_invokes_orchestrator_with_plan_file(mock_ExecutionOrchestrator: MagicMock):
    """
    Tests that the CLI correctly calls the orchestrator with the plan path.
    """
    # ARRANGE
    from datetime import datetime

    mock_orchestrator_instance = MagicMock(spec=ExecutionOrchestrator)
    mock_summary = RunSummary(
        status=RunStatus.SUCCESS,
        start_time=datetime.now(),
        end_time=datetime.now(),
    )
    mock_orchestrator_instance.execute.return_value = ExecutionReport(
        run_summary=mock_summary, action_logs=[]
    )
    mock_ExecutionOrchestrator.return_value = mock_orchestrator_instance

    builder = MarkdownPlanBuilder("Test Plan")
    builder.add_action("READ", params={"Resource": "[a](/a)"})
    valid_plan = builder.build()

    # ACT
    with runner.isolated_filesystem() as temp_dir:
        p = Path(temp_dir) / "plan.md"
        p.write_text(valid_plan, encoding="utf-8")
        result = runner.invoke(app, ["execute", str(p), "--yes"])

    # ASSERT
    assert result.exit_code == 0, f"CLI exited with error: {result.stderr}"
    mock_orchestrator_instance.execute.assert_called_once_with(
        plan_content=valid_plan, interactive=False
    )


@patch("teddy_executor.main.ExecutionOrchestrator")
def test_cli_exits_with_error_code_on_failure(mock_ExecutionOrchestrator: MagicMock):
    """
    Tests that the CLI exits with a non-zero code if the
    execution report indicates a failure.
    """
    # ARRANGE
    from datetime import datetime

    mock_orchestrator_instance = MagicMock(spec=ExecutionOrchestrator)
    mock_summary = RunSummary(
        status=RunStatus.FAILURE,
        start_time=datetime.now(),
        end_time=datetime.now(),
    )
    mock_orchestrator_instance.execute.return_value = ExecutionReport(
        run_summary=mock_summary, action_logs=[]
    )
    mock_ExecutionOrchestrator.return_value = mock_orchestrator_instance

    builder = MarkdownPlanBuilder("Test Plan")
    builder.add_action("READ", params={"Resource": "[a](/a)"})
    valid_plan = builder.build()

    # ACT
    with runner.isolated_filesystem() as temp_dir:
        p = Path(temp_dir) / "plan.md"
        p.write_text(valid_plan, encoding="utf-8")
        result = runner.invoke(app, ["execute", str(p), "--yes"])

    # ASSERT
    assert result.exit_code == 1, (
        f"CLI should exit with code 1 on failure, but got {result.exit_code}"
    )


@patch("teddy_executor.main.ExecutionOrchestrator")
def test_cli_handles_interactive_mode_flag(mock_ExecutionOrchestrator: MagicMock):
    """
    Tests that the CLI correctly sets the interactive flag (default is True).
    """
    # ARRANGE
    from datetime import datetime

    mock_orchestrator_instance = MagicMock(spec=ExecutionOrchestrator)
    mock_summary = RunSummary(
        status=RunStatus.SUCCESS,
        start_time=datetime.now(),
        end_time=datetime.now(),
    )
    mock_orchestrator_instance.execute.return_value = ExecutionReport(
        run_summary=mock_summary, action_logs=[]
    )
    mock_ExecutionOrchestrator.return_value = mock_orchestrator_instance

    builder = MarkdownPlanBuilder("Test Plan")
    builder.add_action("READ", params={"Resource": "[a](/a)"})
    valid_plan = builder.build()

    # ACT
    with runner.isolated_filesystem() as temp_dir:
        p = Path(temp_dir) / "plan.md"
        p.write_text(valid_plan, encoding="utf-8")
        # Note: No --yes flag
        runner.invoke(app, ["execute", str(p)])

    # ASSERT
    mock_orchestrator_instance.execute.assert_called_once_with(
        plan_content=valid_plan, interactive=True
    )
