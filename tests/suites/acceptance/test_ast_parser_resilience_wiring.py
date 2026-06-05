"""Acceptance tests for AST parser resilience (Slice 02-11)."""

import textwrap
from unittest.mock import Mock

from teddy_executor.core.domain.models.shell_output import ShellOutput
from teddy_executor.core.ports.outbound.shell_executor import IShellExecutor
from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter


def test_parser_resilience_handles_both_artifacts(tmp_path, monkeypatch):
    """
    Scenario: Plan contains a valid action whose closing fence line has trailing
    text AND a trailing unexpected code block after the last action.
    When the plan is parsed and executed,
    Then both artifacts are handled gracefully → SUCCESS with correct action content.
    """
    # Arrange
    env = TestEnvironment(monkeypatch, tmp_path).setup()
    # Override the shell mock to return success for the dummy EXECUTE command
    mock_shell = Mock(spec=IShellExecutor)
    mock_shell.execute.return_value = ShellOutput(
        return_code=0, stdout="success", stderr=""
    )
    env.container.register(IShellExecutor, lambda: mock_shell)

    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # Plan components:
    # 1. An EXECUTE action whose tilde-fenced code block has trailing text on
    #    the closing fence ("~~~~~~ trailing extra text").
    # 2. A trailing unexpected code block after the action plan.
    plan = textwrap.dedent("""\
        # Test Plan
        - **Agent:** Dev
        - **Plan Type:** Test
        - **Status:** Pending

        ## Rationale
        ~~~~~~~~~
        test rationale
        ~~~~~~~~~

        ## Action Plan

        ### `EXECUTE`
        - **Description:** Dummy command.
        ~~~~~~shell
        echo success
        ~~~~~~ trailing extra text

        ~~~~~~~~~
        This is an unexpected trailing code block after the last action.
        ~~~~~~~~~
    """)

    # Act
    result = adapter.run_command(["execute", "--plan-content", plan])

    # Assert
    assert result.exit_code == 0, (
        f"CLI should exit with 0 (SUCCESS). Got stdout:\n{result.stdout}"
    )

    output = result.stdout + result.stderr
    # Verify the overall report indicates success
    assert "SUCCESS" in output, f"Expected 'SUCCESS' in output. Got:\n{output}"
    # Verify the command executed
    assert "echo success" in output, (
        f"Expected command 'echo success' in output. Got:\n{output}"
    )
