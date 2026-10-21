"""Acceptance coverage for the workspace startup gates.

The public ``teddy start`` entry point must honour the ``workspace`` toggles
from the resolved configuration. A disabled gate skips its startup step and
prints exactly one warning naming the real consequence.
"""

from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.setup.test_environment import TestEnvironment


PRE_COMMIT_WARNING = (
    "⚠ Pre-commit hook installation is disabled. "
    "The post-commit test gate will not run."
)
INIT_WARNING = "⚠ Git repository not initialized. Version control actions will fail."


def _write_workspace_config(tmp_path, text: str) -> None:
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir(exist_ok=True)
    (teddy_dir / "config.yaml").write_text(text, encoding="utf-8")


def test_start_warns_when_both_workspace_gates_are_disabled(tmp_path, monkeypatch):
    """Both disabled gates emit one warning each and skip their startup steps."""
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
    assert PRE_COMMIT_WARNING in output
    assert INIT_WARNING in output
