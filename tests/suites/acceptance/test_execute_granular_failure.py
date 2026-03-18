import sys
from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder

from teddy_executor.adapters.outbound.shell_adapter import ShellAdapter
from teddy_executor.core.ports.outbound import IShellExecutor


def test_execute_reports_specific_failing_command_in_multiline_block(
    tmp_path, monkeypatch
):
    """Scenario: Granular EXECUTE failure identifies the specific command that failed in a multi-line block."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    # Register a real shell adapter to test actual shell-side error trapping
    env.container.register(IShellExecutor, ShellAdapter)

    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # Use python -c for cross-platform failure behavior
    cmd = f"{sys.executable} -c \"print('first')\"\n"
    cmd += f"{sys.executable} -c \"import sys; print('second'); sys.exit(1)\"\n"
    cmd += f"{sys.executable} -c \"print('third')\""

    plan = (
        MarkdownPlanBuilder("Granular Failure Test")
        .add_execute(cmd, description="Multi-line command where middle fails")
        .build()
    )

    result = adapter.run_execute_with_plan(plan, tmp_path, input="y\n")

    assert result.exit_code != 0
    # The report detail should explicitly identify the second command as the failure point
    assert "- **Failed Command:**" in result.stdout
    assert "sys.exit(1)" in result.stdout
