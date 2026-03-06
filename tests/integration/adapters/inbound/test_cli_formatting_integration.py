from typer.testing import CliRunner
from teddy_executor.__main__ import app

runner = CliRunner()


def test_cli_help_output():
    """Verify the help output is available."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Usage: " in result.stdout


def test_cli_version_output():
    """Verify version command (placeholder for now)."""
    # This is a dummy test to help balance the pyramid
    result = runner.invoke(app, ["--help"])
    assert "execute" in result.stdout
