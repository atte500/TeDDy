import sys
from pathlib import Path
from tests.drivers.plan_builder import MarkdownPlanBuilder
from tests.drivers.cli_adapter import CliTestAdapter
from tests.setup.test_environment import TestEnvironment


def test_execute_allows_chaining_and_directives_in_command_block(
    tmp_path: Path, monkeypatch
):
    """Scenario: EXECUTE allows shell chaining (&&) and directory changes (cd)."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup().with_real_shell()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    cmd = (
        f"{sys.executable} -c \"import os; os.makedirs('temp_relaxed', exist_ok=True)\" && "
        f"cd temp_relaxed && "
        f"{sys.executable} -c \"open('success.txt', 'w').close()\" && "
        f"{sys.executable} -c \"import os; print('success.txt' if os.path.exists('success.txt') else 'fail')\""
    )

    plan = (
        MarkdownPlanBuilder("Relaxed Protocol")
        .add_execute(cmd, description="Chained command with cd")
        .build()
    )

    report = adapter.execute_plan(plan)

    assert report.action_was_successful(0)
    assert "success.txt" in report.stdout


def test_execute_maintains_statelessness_between_blocks(tmp_path: Path, monkeypatch):
    """Scenario: Directory changes and side effects do not persist between separate EXECUTE blocks."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup().with_real_shell()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    cmd1 = f"{sys.executable} -c \"import os; os.makedirs('temp_stateless', exist_ok=True); open(os.path.join('temp_stateless', 'inside.txt'), 'w').close()\""
    cmd2 = f"{sys.executable} -c \"import os; import sys; exists = os.path.exists('inside.txt'); print('File found' if exists else 'File not found'); sys.exit(0 if exists else 1)\""

    plan = (
        MarkdownPlanBuilder("Statelessness Test")
        .add_execute(cmd1, description="Create dir and file")
        .add_execute(cmd2, description="Check for file in root")
        .build()
    )

    report = adapter.execute_plan(plan)

    assert report.action_was_successful(0)
    assert report.action_logs[1].status == "FAILURE"
    assert "File not found" in report.stdout
