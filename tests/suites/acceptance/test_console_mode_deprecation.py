"""Acceptance gate for the deprecation of the console plan-review path.

This is the final behavioral gate for the console-mode deprecation slice. It
drives the outermost CLI boundary (Subcutaneous Testing) to prove that:

1. The deprecated --console / --tui flags are absent from the start, resume,
   and execute help surfaces.
2. An interactive plan review proceeds end-to-end without any console flag,
   through the harness reviewer that stands in for the removed console reviewer.
"""

import pytest

from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.setup.test_environment import TestEnvironment


@pytest.mark.parametrize("command", ["start", "resume", "execute"])
def test_help_omits_deprecated_console_and_tui_flags(
    env: TestEnvironment, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    """The deprecated console/TUI mode flags are gone from every help surface."""
    env.setup()
    assert env.workspace is not None
    adapter = CliTestAdapter(monkeypatch, env.workspace)

    result = adapter.run_cli_command([command, "--help"])

    assert result.exit_code == 0, result.output
    # Defeat a vacuous pass: the help surface must actually render.
    assert "Usage" in result.stdout
    assert "--console" not in result.stdout
    assert "--tui" not in result.stdout


def test_interactive_plan_review_runs_flag_free_end_to_end(
    env: TestEnvironment, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An interactive review proceeds end-to-end with no console flag supplied."""
    env.setup().with_real_filesystem().with_real_system_environment().with_real_shell().with_real_interactor()
    assert env.workspace is not None

    plan_content = (
        MarkdownPlanBuilder("Flag-Free Gateway Plan")
        .add_execute("echo gateway-ok", description="Verify the flag-free path")
        .build()
    )
    plan_path = env.workspace / "gateway-plan.md"
    plan_path.write_text(plan_content, encoding="utf-8")

    adapter = CliTestAdapter(monkeypatch, env.workspace)

    result = adapter.run_cli_command(
        ["execute", "gateway-plan.md", "--no-copy"], input="y\n"
    )

    assert result.exit_code == 0, result.output
    assert "Overall Status" in result.stdout
