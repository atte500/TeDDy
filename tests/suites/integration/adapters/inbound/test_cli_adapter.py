from datetime import datetime
from unittest.mock import MagicMock
from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from teddy_executor.core.domain.models import (
    ExecutionReport,
    RunSummary,
    RunStatus,
)
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase


def test_cli_invokes_orchestrator_with_plan_file(monkeypatch, tmp_path):
    """
    Tests that the CLI correctly calls the orchestrator with the plan path.
    """
    # ARRANGE
    env = TestEnvironment(monkeypatch, tmp_path).setup()
    cli = CliTestAdapter(monkeypatch, cwd=tmp_path)

    mock_run_plan = MagicMock(spec=IRunPlanUseCase)
    env.container.register(IRunPlanUseCase, instance=mock_run_plan)

    mock_summary = RunSummary(
        status=RunStatus.SUCCESS,
        start_time=datetime.now(),
        end_time=datetime.now(),
    )
    mock_run_plan.execute.return_value = ExecutionReport(
        run_summary=mock_summary, action_logs=[]
    )

    valid_plan = MarkdownPlanBuilder("Test Plan").add_read("a").build()

    # Create the file referenced in the plan so validation passes
    (tmp_path / "a").write_text("content", encoding="utf-8")
    p = tmp_path / "plan.md"
    p.write_text(valid_plan, encoding="utf-8")

    # ACT
    result = cli.run_cli_command(["execute", str(p), "--yes"])

    # ASSERT
    assert result.exit_code == 0, f"CLI exited with error: {result.stderr}"
    _, kwargs = mock_run_plan.execute.call_args
    assert kwargs["plan_path"] is not None
    assert kwargs["interactive"] is False


def test_cli_exits_with_error_code_on_failure(monkeypatch, tmp_path):
    """
    Tests that the CLI exits with a non-zero code if the
    execution report indicates a failure.
    """
    # ARRANGE
    env = TestEnvironment(monkeypatch, tmp_path).setup()
    cli = CliTestAdapter(monkeypatch, cwd=tmp_path)

    mock_run_plan = MagicMock(spec=IRunPlanUseCase)
    env.container.register(IRunPlanUseCase, instance=mock_run_plan)

    mock_summary = RunSummary(
        status=RunStatus.FAILURE,
        start_time=datetime.now(),
        end_time=datetime.now(),
    )
    mock_run_plan.execute.return_value = ExecutionReport(
        run_summary=mock_summary, action_logs=[]
    )

    valid_plan = MarkdownPlanBuilder("Test Plan").add_read("a").build()

    (tmp_path / "a").write_text("content", encoding="utf-8")
    p = tmp_path / "plan.md"
    p.write_text(valid_plan, encoding="utf-8")

    # ACT
    result = cli.run_cli_command(["execute", str(p), "--yes"])

    # ASSERT
    assert result.exit_code == 1


def test_cli_handles_interactive_mode_flag(monkeypatch, tmp_path):
    """
    Tests that the CLI correctly sets the interactive flag (default is True).
    """
    # ARRANGE
    env = TestEnvironment(monkeypatch, tmp_path).setup()
    cli = CliTestAdapter(monkeypatch, cwd=tmp_path)

    mock_run_plan = MagicMock(spec=IRunPlanUseCase)
    env.container.register(IRunPlanUseCase, instance=mock_run_plan)

    mock_summary = RunSummary(
        status=RunStatus.SUCCESS,
        start_time=datetime.now(),
        end_time=datetime.now(),
    )
    mock_run_plan.execute.return_value = ExecutionReport(
        run_summary=mock_summary, action_logs=[]
    )

    valid_plan = MarkdownPlanBuilder("Test Plan").add_read("a").build()

    (tmp_path / "a").write_text("content", encoding="utf-8")
    p = tmp_path / "plan.md"
    p.write_text(valid_plan, encoding="utf-8")

    # ACT
    cli.run_cli_command(["execute", str(p)])

    # ASSERT
    _, kwargs = mock_run_plan.execute.call_args
    assert kwargs["interactive"] is True
