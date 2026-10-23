"""Acceptance coverage for the workspace startup gates.

The public ``teddy start`` entry point must honour the ``workspace`` toggles
from the resolved configuration. A disabled gate skips its startup step and
prints no reminder, because the opt-out is the user's own choice.
"""

from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.setup.test_environment import TestEnvironment


PRE_COMMIT_REMINDER = "Pre-commit hook installation is disabled"
INIT_REMINDER = "Git repository not initialized"
NOT_A_REPOSITORY_WARNING = "⚠ Workspace pull skipped: not a Git repository."


def _write_workspace_config(tmp_path, text: str) -> None:
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir(exist_ok=True)
    (teddy_dir / "config.yaml").write_text(text, encoding="utf-8")


def test_start_silences_both_disabled_workspace_gates(tmp_path, monkeypatch):
    """Both disabled gates skip their startup steps without a reminder."""
    # Arrange
    (
        TestEnvironment(monkeypatch, tmp_path)
        .setup()
        .with_real_shell()
        .with_real_filesystem()
        .with_real_init_service()
        .with_real_config()
    )
    _write_workspace_config(
        tmp_path,
        "workspace:\n  init: false\n  pre-commit: false\n",
    )
    # The mocked planning response reads README.md, so a stub file keeps the
    # turn deterministic instead of driving a replan loop.
    (tmp_path / "README.md").write_text("# Workspace\n", encoding="utf-8")
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # Act
    result = adapter.run_cli_command(
        ["start", "workspace-gates", "-a", "developer", "-m", "Test gates"],
        input="n\n",
    )

    # Assert
    output = result.stdout + result.stderr
    assert result.exit_code == 0, output
    assert PRE_COMMIT_REMINDER not in output
    assert INIT_REMINDER not in output
    assert NOT_A_REPOSITORY_WARNING in output
