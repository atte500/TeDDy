from typer.testing import CliRunner
from teddy_executor.__main__ import app

runner = CliRunner()


def test_cli_help_is_descriptive_and_accurate():
    """
    Scenario: CLI help is descriptive and accurate
    - Given the teddy CLI
    - When a user runs `teddy --help` or `teddy execute --help`
    - Then the output contains clear descriptions for all commands and options.
    - And the descriptions accurately reflect the project's root-relative path requirements.
    """
    # 1. Test top-level help
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    # Ensure commands are listed
    assert "execute" in result.stdout
    assert "context" in result.stdout
    assert "get-prompt" in result.stdout

    # 2. Test execute help specifically for root-relative mentions
    result_execute = runner.invoke(app, ["execute", "--help"])
    assert result_execute.exit_code == 0
    # The requirement is that it mentions "root-relative"
    assert "root-relative" in result_execute.stdout.lower()

    # 3. Test context help for root-relative mentions (it gathers context from root)
    result_context = runner.invoke(app, ["context", "--help"])
    assert result_context.exit_code == 0
    assert "root-relative" in result_context.stdout.lower()
