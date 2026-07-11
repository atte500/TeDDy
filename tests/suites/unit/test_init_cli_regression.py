"""
Regression test for bug #11: "Prompts: unchanged." despite overwrites.

Tests via CliRunner to avoid global patching and bare MagicMock.

Verifies:
- `teddy init` (no subcommand) prints full summary.
- `teddy init prompts` prints only the prompts subcommand output,
  without any "Prompts: unchanged." message.
"""

import os
import tempfile
from pathlib import Path

from typer.testing import CliRunner

from teddy_executor.__main__ import app

runner = CliRunner()


def setup_teddy_dir(temp_dir: str) -> None:
    """Create a .teddy directory with existing config and prompts files."""
    teddy_path = Path(temp_dir) / ".teddy"
    prompts_path = teddy_path / "prompts"
    prompts_path.mkdir(parents=True, exist_ok=True)
    prompt_files = [
        "architect.xml",
        "assistant.xml",
        "debugger.xml",
        "developer.xml",
        "pathfinder.xml",
        "prototyper.xml",
    ]
    for fname in prompt_files:
        (prompts_path / fname).write_text("<!-- existing prompt -->", encoding="utf-8")
    (teddy_path / "config.yaml").write_text("config: existing", encoding="utf-8")
    (teddy_path / ".gitignore").write_text("*.pyc", encoding="utf-8")
    (teddy_path / "init.context").write_text("existing context", encoding="utf-8")


class TestInitCliRegression:
    """Regression tests for init callback and subcommand output."""

    def test_init_no_subcommand_prints_summary(self):
        """
        `teddy init` without subcommand should print the full summary
        including "Prompts:" status.
        """
        with tempfile.TemporaryDirectory(prefix="teddy_regression_") as tmpdir:
            setup_teddy_dir(tmpdir)
            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                result = runner.invoke(app, ["init"])
                assert result.exit_code == 0, f"Non-zero exit: {result.stderr}"
                assert "TeDDy initialized in .teddy folder." in result.stdout
                assert "Config:" in result.stdout
                assert "Prompts:" in result.stdout
                # The summary should contain "unchanged" since we set up files
                assert "unchanged" in result.stdout
            finally:
                os.chdir(original_cwd)

    def test_init_prompts_no_conflicting_message(self):
        """
        `teddy init prompts` should NOT print a line containing
        "Prompts: unchanged."  It should only print the subcommand output.
        """
        with tempfile.TemporaryDirectory(prefix="teddy_regression_") as tmpdir:
            setup_teddy_dir(tmpdir)
            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                result = runner.invoke(app, ["init", "prompts"])
                assert result.exit_code == 0, f"Non-zero exit: {result.stderr}"
                # The subcommand output should contain "Prompts overwritten"
                assert "Prompts overwritten (6 files)." in result.stdout
                # There should be no "Prompts: unchanged." (either from callback summary
                # or the subcommand). The callback should skip when subcommand active.
                assert (
                    "Prompts: unchanged." not in result.stdout
                ), "Conflicting 'Prompts: unchanged.' found in output!"
            finally:
                os.chdir(original_cwd)
