import os
import textwrap
from pathlib import Path

from typer.testing import CliRunner


from teddy_executor.main import app
from tests.acceptance.plan_builder import MarkdownPlanBuilder

runner = CliRunner()


def test_execute_action_report_shows_description():
    """
    Verify that the `EXECUTE` action log in the report includes
    the description from the plan.
    """
    plan = (
        MarkdownPlanBuilder("Test Plan")
        .add_action(
            "execute",
            {
                "Description": "My Test Command",
                "command": "echo 'hello'",
            },
        )
        .build()
    )

    result = runner.invoke(
        app,
        ["execute", "--plan-content", plan],
        input="y\n",  # Approve the action
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert '#### `EXECUTE` on "My Test Command"' in result.stdout


def test_read_action_shows_correct_resource_path(tmp_path: Path):
    """
    Given a plan with a successful READ action,
    When the plan is executed,
    Then the final report's ## Resource Contents section must correctly identify the resource path.
    """
    # GIVEN
    test_file = tmp_path / "test_read_file.txt"
    test_file.write_text("Hello from the test file.")

    plan_content = textwrap.dedent(f"""
    # Test Plan
    - **Agent:** Developer

    ## Rationale
    ````text
    Test
    ````

    ## Action Plan
    ### `READ`
    - **Resource:** [{test_file.name}](/{test_file.name})
    - **Description:** Read a test file.
    """)

    # WHEN
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(
            app,
            ["execute", "--plan-content", plan_content, "-y"],
            catch_exceptions=False,
        )
    finally:
        os.chdir(original_cwd)

    # THEN
    assert result.exit_code == 0
    output = result.stdout
    assert "## Resource Contents" in output
    # The parser now normalizes the path, so we expect the relative path in the report.
    # The template renders it as a link inside backticks.
    expected_resource = f"**Resource:** `[{test_file.name}](/{test_file.name})`"
    assert expected_resource in output
    assert "Hello from the test file." in output
