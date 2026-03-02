import pytest
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
from teddy_executor.__main__ import app
from teddy_executor.container import create_container

runner = CliRunner()


@pytest.fixture
def fresh_container():
    """Provides a fresh container for each test and patches the global one in __main__."""
    c = create_container()
    with patch("teddy_executor.__main__.container", c):
        yield c


def test_cli_invokes_orchestrator_with_plan_file(fresh_container):
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

    # Register the mock instance in the container
    fresh_container.register(ExecutionOrchestrator, instance=mock_orchestrator_instance)

    builder = MarkdownPlanBuilder("Test Plan")
    builder.add_action("READ", params={"Resource": "[a](/a)"})
    valid_plan = builder.build()

    # ACT
    with runner.isolated_filesystem() as temp_dir:
        # Create the file referenced in the plan so validation passes
        (Path(temp_dir) / "a").write_text("content", encoding="utf-8")

        p = Path(temp_dir) / "plan.md"
        p.write_text(valid_plan, encoding="utf-8")
        result = runner.invoke(app, ["execute", str(p), "--yes"])

    # ASSERT
    from unittest.mock import ANY

    assert result.exit_code == 0, f"CLI exited with error: {result.stderr}"
    mock_orchestrator_instance.execute.assert_called_once_with(
        plan=ANY, interactive=False
    )


def test_cli_exits_with_error_code_on_failure(fresh_container):
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

    fresh_container.register(ExecutionOrchestrator, instance=mock_orchestrator_instance)

    builder = MarkdownPlanBuilder("Test Plan")
    builder.add_action("READ", params={"Resource": "[a](/a)"})
    valid_plan = builder.build()

    # ACT
    with runner.isolated_filesystem() as temp_dir:
        # Create the file referenced in the plan so validation passes
        (Path(temp_dir) / "a").write_text("content", encoding="utf-8")

        p = Path(temp_dir) / "plan.md"
        p.write_text(valid_plan, encoding="utf-8")
        result = runner.invoke(app, ["execute", str(p), "--yes"])

    # ASSERT
    assert result.exit_code == 1, (
        f"CLI should exit with code 1 on failure, but got {result.exit_code}"
    )


def test_cli_handles_interactive_mode_flag(fresh_container):
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

    fresh_container.register(ExecutionOrchestrator, instance=mock_orchestrator_instance)

    builder = MarkdownPlanBuilder("Test Plan")
    builder.add_action("READ", params={"Resource": "[a](/a)"})
    valid_plan = builder.build()

    # ACT
    with runner.isolated_filesystem() as temp_dir:
        # Create the file referenced in the plan so validation passes
        (Path(temp_dir) / "a").write_text("content", encoding="utf-8")

        p = Path(temp_dir) / "plan.md"
        p.write_text(valid_plan, encoding="utf-8")
        # Note: No --yes flag
        runner.invoke(app, ["execute", str(p)])

    # ASSERT
    from unittest.mock import ANY

    mock_orchestrator_instance.execute.assert_called_once_with(
        plan=ANY, interactive=True
    )
