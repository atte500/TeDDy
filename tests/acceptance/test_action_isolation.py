import textwrap
from typer.testing import CliRunner
from teddy_executor.__main__ import app

runner = CliRunner()


def test_isolated_terminal_action_executes_normally():
    """
    Scenario 1: Isolated Terminal Action executes normally
    Given a plan with a single action of type PROMPT
    When teddy execute is run
    Then the PROMPT action should be executed.
    """
    plan_content = textwrap.dedent("""
        # Isolated Prompt
        - Status: Green 🟢
        - Plan Type: User Verification
        - Agent: Developer

        ## Rationale
        ```text
        Testing isolated prompt.
        ```

        ## Action Plan

        ### PROMPT
        Please confirm this isolated prompt.
    """).strip()
    # We use --plan-content to provide the plan and -y to auto-approve.
    # PROMPT action always requires user input in interactive mode.
    # In this test, we simulate user interaction by providing "y" to the input.
    result = runner.invoke(
        app, ["execute", "--plan-content", plan_content], input="y\n"
    )

    assert result.exit_code == 0
    # Check that the PROMPT action appears in the Action Log of the report
    assert "### `PROMPT`" in result.stdout
    assert "- **Status:** SUCCESS" in result.stdout
    # Check that it wasn't skipped
    assert "SKIPPED" not in result.stdout


def test_terminal_action_is_skipped_in_multi_action_plan(tmp_path, monkeypatch):
    """
    Scenario 2: Terminal Action is skipped in multi-action plan
    Given a plan with a CREATE action and a PROMPT action
    When teddy execute is run
    Then the CREATE action should be executed normally
    And the PROMPT action should be marked as SKIPPED
    And the skip reason should be: "Action must be executed in isolation to ensure state consistency."
    """
    filename = "new_file.txt"
    plan_content = textwrap.dedent(f"""
        # Multi-action Plan
        - Status: Green 🟢
        - Plan Type: Implementation
        - Agent: Developer

        ## Rationale
        ```text
        Testing multi-action isolation.
        ```

        ## Action Plan

        ### `CREATE`
        - **File Path:** {filename}
        - **Description:** Creating a file.
        ````text
        File content.
        ````

        ### `PROMPT`
        Please confirm this non-isolated prompt.
    """).strip()
    # Use -y to auto-approve the CREATE action.
    # If isolation logic is NOT working, it will then prompt for the non-isolated PROMPT.
    # We provide 'y' just in case it fails to skip, but we assert on the skip status.
    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        result = runner.invoke(
            app, ["execute", "--yes", "--plan-content", plan_content], input="y\n"
        )

    assert result.exit_code == 0, f"CLI failed with stdout: {result.stdout}"
    # CREATE should succeed
    assert "### `CREATE`" in result.stdout
    assert "- **Status:** SUCCESS" in result.stdout
    assert (tmp_path / filename).exists()

    # PROMPT should be SKIPPED
    assert "### `PROMPT`" in result.stdout
    assert "- **Status:** SKIPPED" in result.stdout
    assert (
        "Action must be executed in isolation to ensure state consistency."
        in result.stdout
    )
