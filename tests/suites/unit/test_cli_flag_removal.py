"""Unit tests for CLI flag removal (Seam: --provider flag)."""

from typer.testing import CliRunner
from teddy_executor.__main__ import app


class TestCliFlagProvider:
    """Tests that the --provider flag is removed from CLI help output."""

    def test_provider_flag_not_in_start_help(self):
        """The --provider flag must not appear in 'teddy start --help' output."""
        runner = CliRunner()
        result = runner.invoke(app, ["start", "--help"])
        assert result.exit_code == 0, f"Help invocation failed: {result.output}"
        # The flag should be absent from the help text
        assert "--provider" not in result.output, (
            f"--provider flag still present in 'start --help':\n{result.output}"
        )

    def test_provider_flag_not_in_resume_help(self):
        """The --provider flag must not appear in 'teddy resume --help' output."""
        runner = CliRunner()
        result = runner.invoke(app, ["resume", "--help"])
        assert result.exit_code == 0, f"Help invocation failed: {result.output}"
        assert "--provider" not in result.output, (
            f"--provider flag still present in 'resume --help':\n{result.output}"
        )
