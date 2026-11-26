"""Acceptance tests: an interrupted stateless ``execute`` run.

A stateless run owns the same two-phase interrupt bracket the session loop
owns, so a press drains the plan instead of printing a traceback, the report
records ``INTERRUPTED``, and the previous SIGINT disposition is restored.
"""

import signal

from teddy_executor.core.domain.models.shell_output import ShellOutput
from teddy_executor.core.ports.outbound.shell_executor import IShellExecutor
from teddy_executor.core.utils.interrupt_guard import raise_interrupt
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.observers.report_parser import ReportParser
from tests.harness.setup.fake_shell_executor import FakeShellExecutor
from tests.harness.setup.sigint_delivery import (
    SigintDeliveryMode,
    stub_sigint_delivery,
)
from tests.harness.setup.test_environment import TestEnvironment


def test_interrupted_execute_run_reports_interrupted_and_restores_disposition(
    monkeypatch, tmp_path
):
    """Scenario: Ctrl+C during a long EXECUTE ends the run cleanly.

    The press fires from inside the fake shell's ``execute()``, which is where
    the orchestrator holds its EXECUTING phase, so the guard records a drain
    instead of raising and the report still gets assembled.
    """
    # Arrange
    env = TestEnvironment(monkeypatch, tmp_path).setup()

    def press_ctrl_c_and_report_killed(command: str) -> ShellOutput:
        raise_interrupt()
        return ShellOutput(stdout="", stderr="", return_code=-2, interrupted=True)

    shell = FakeShellExecutor(on_execute=press_ctrl_c_and_report_killed)
    env.container.register(IShellExecutor, lambda: shell)
    delivered = stub_sigint_delivery(
        monkeypatch, mode=SigintDeliveryMode.ROUTE_TO_HANDLER
    )
    previous_disposition = signal.getsignal(signal.SIGINT)
    plan = (
        MarkdownPlanBuilder("Interruptible Run")
        .add_execute("sleep 30", description="Long-running command")
        .build()
    )

    try:
        # Act
        result = CliTestAdapter(monkeypatch, tmp_path).run_execute_with_plan(
            plan_content=plan
        )
    finally:
        signal.signal(signal.SIGINT, previous_disposition)

    # Assert: the press was delivered, the boundary named the key, the audit
    # trail records the drain, and nothing escaped as a traceback.
    combined = result.stdout + result.stderr
    assert sent_presses(delivered)
    assert result.exit_code == 0, combined
    assert "Interrupted by user (Ctrl+C)" in combined
    assert "Traceback" not in combined
    report = ReportParser(combined)
    assert report.run_summary["Overall Status"] == "INTERRUPTED"
    assert report.action_logs[0].status == "INTERRUPTED"
    assert shell.commands == ["sleep 30"]
    assert signal.getsignal(signal.SIGINT) is previous_disposition


def sent_presses(delivered: list[int]) -> bool:
    """Report whether exactly one SIGINT press reached the delivery recorder."""
    return delivered == [signal.SIGINT]
