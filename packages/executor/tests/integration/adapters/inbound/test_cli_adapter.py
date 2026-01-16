from pathlib import Path
from unittest.mock import MagicMock, patch

import punq
from typer.testing import CliRunner

from teddy_executor.core.domain.models import (
    ExecutionReport,
    RunSummary,
    RunStatus,
)
from teddy_executor.core.ports.inbound.run_plan_use_case import RunPlanUseCase
from teddy_executor.main import app

runner = CliRunner(mix_stderr=False)


def test_cli_invokes_orchestrator_with_plan_file():
    """
    Tests that the CLI correctly calls the orchestrator with the plan path.
    """
    # ARRANGE
    from datetime import datetime

    mock_orchestrator = MagicMock(spec=RunPlanUseCase)
    mock_summary = RunSummary(
        status=RunStatus.SUCCESS,
        start_time=datetime.now(),
        end_time=datetime.now(),
    )
    mock_orchestrator.execute.return_value = ExecutionReport(
        run_summary=mock_summary, action_logs=[]
    )

    test_container = punq.Container()
    test_container.register(RunPlanUseCase, instance=mock_orchestrator)

    # ACT
    with runner.isolated_filesystem() as temp_dir:
        p = Path(temp_dir) / "plan.yml"
        p.write_text("plan content")

        with patch("teddy_executor.main.container", test_container):
            result = runner.invoke(app, ["execute", str(p), "--yes"])

    # ASSERT
    assert result.exit_code == 0, f"CLI exited with error: {result.stderr}"
    mock_orchestrator.execute.assert_called_once_with(
        plan_content="plan content", interactive=False
    )


def test_cli_exits_with_error_code_on_failure():
    """
    Tests that the CLI exits with a non-zero code if the
    execution report indicates a failure.
    """
    # ARRANGE
    from datetime import datetime

    mock_orchestrator = MagicMock(spec=RunPlanUseCase)
    mock_summary = RunSummary(
        status=RunStatus.FAILURE,
        start_time=datetime.now(),
        end_time=datetime.now(),
    )
    mock_orchestrator.execute.return_value = ExecutionReport(
        run_summary=mock_summary, action_logs=[]
    )

    test_container = punq.Container()
    test_container.register(RunPlanUseCase, instance=mock_orchestrator)

    # ACT
    with runner.isolated_filesystem() as temp_dir:
        p = Path(temp_dir) / "plan.yml"
        p.write_text("any plan")

        with patch("teddy_executor.main.container", test_container):
            result = runner.invoke(app, ["execute", str(p), "--yes"])

    # ASSERT
    assert result.exit_code == 1, (
        f"CLI should exit with code 1 on failure, but got {result.exit_code}"
    )


def test_cli_handles_interactive_mode_flag():
    """
    Tests that the CLI correctly sets the interactive flag (default is True).
    """
    # ARRANGE
    from datetime import datetime

    mock_orchestrator = MagicMock(spec=RunPlanUseCase)
    mock_summary = RunSummary(
        status=RunStatus.SUCCESS,
        start_time=datetime.now(),
        end_time=datetime.now(),
    )
    mock_orchestrator.execute.return_value = ExecutionReport(
        run_summary=mock_summary, action_logs=[]
    )

    test_container = punq.Container()
    test_container.register(RunPlanUseCase, instance=mock_orchestrator)

    # ACT
    with runner.isolated_filesystem() as temp_dir:
        p = Path(temp_dir) / "plan.yml"
        p.write_text("plan content")

        with patch("teddy_executor.main.container", test_container):
            # Note: No --yes flag
            runner.invoke(app, ["execute", str(p)])

    # ASSERT
    mock_orchestrator.execute.assert_called_once_with(
        plan_content="plan content", interactive=True
    )
