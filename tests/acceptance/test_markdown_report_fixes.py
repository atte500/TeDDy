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
    # New format: ### `EXECUTE`: "My Test Command"
    assert '### `EXECUTE`: "My Test Command"' in result.stdout


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
    # New format: H3 Header with link.
    expected_resource = f"### [{test_file.name}](/{test_file.name})"
    assert expected_resource in output
    assert "Hello from the test file." in output


def test_failed_edit_action_reports_file_content(tmp_path: Path):
    """
    Scenario 3: Failed EDIT action reports file content
    - Given a plan with an EDIT action that will fail during execution (e.g., due to a permissions error).
    - When the plan is executed.
    - Then the final report must contain a '## Failed Action Details' section.
    - And this section must include the full, current content of the file that the EDIT action failed to modify.
    """
    # GIVEN
    # A file with known content that will be made read-only
    file_content = textwrap.dedent("""
        [tool.poetry]
        name = "my-project"
        version = "0.1.0"
    """).strip()
    target_file_name = "pyproject.toml"
    target_file = tmp_path / target_file_name
    target_file.write_text(file_content, encoding="utf-8")
    os.chmod(target_file, 0o444)  # Make read-only to cause runtime failure

    # A plan with a RELATIVE path that will pass validation but fail at runtime
    plan_content = textwrap.dedent(f"""
        # Edit pyproject.toml
        - **Agent:** Developer

        ## Action Plan
        ### `EDIT`
        - **File Path:** {target_file_name}
        - **Description:** Update the project name.

        #### `FIND:`
        ```toml
        name = "my-project"
        ```
        #### `REPLACE:`
        ```toml
        name = "new-project-name"
        ```
    """).strip()

    # WHEN
    # We must change into the temp directory so the relative path resolves correctly.
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
    assert result.exit_code != 0, "Command should fail"
    report = result.stdout

    # AND the report must contain a Resource Contents section with the file content
    assert "## Failed Action Details" not in report, (
        "Report contains deprecated failed details section"
    )
    # New format: ### `EDIT`: [pyproject.toml](/pyproject.toml)
    # Note: The template now uses the path link in the header
    assert f"### `EDIT`: [{target_file_name}](/{target_file_name})" in report, (
        "Report missing correct action title with file link in summary"
    )
    assert "## Resource Contents" in report, "Report missing resource contents section"
    # New format: H3 Header with link.
    assert f"### [{target_file_name}](/{target_file_name})" in report, (
        "Report missing correct resource link"
    )
    assert file_content in report, "File content not found in report"


def test_edit_validation_failure_reports_file_content(tmp_path: Path):
    """
    Given an EDIT action that will fail validation (FIND block mismatch)
    When the plan is executed
    Then the validation failure report must include the content of the target file.
    """
    # GIVEN a file with known content
    file_path = tmp_path / "hello.txt"
    file_content = "Hello, world!"
    file_path.write_text(file_content)

    # AND a plan with an EDIT action with a FIND block that won't match
    # Note: Using a relative path, so we must execute from within tmp_path
    plan_content = textwrap.dedent(f"""
        # Test Plan
        - **Agent:** Developer
        ## Action Plan
        ### `EDIT`
        - **File Path:** {file_path.name}
        #### `FIND:`
        ```text
        This will not be found.
        ```
        #### `REPLACE:`
        ```text
        This doesn't matter.
        ```
    """).strip()

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

    # THEN the command should fail
    assert result.exit_code != 0
    report = result.stdout

    # AND the report should indicate validation failure
    assert "- **Overall Status:** Validation Failed" in report
    assert "The `FIND` block could not be located in the file" in report

    # AND the report MUST contain the original content of the file
    assert file_content in report, "File content not found in validation failure report"


def test_smart_fencing_in_report():
    """
    Given an EXECUTE action that outputs triple backticks,
    When the report is generated,
    Then the stdout block in the report must be fenced with quad backticks (or more).
    """
    # GIVEN a plan that echoes triple backticks
    # Note: We use single quotes in the echo command to avoid shell expansion errors
    # AND we use quad backticks for the plan's code block to allow nesting triple backticks inside
    plan_content = textwrap.dedent("""
        # Smart Fence Test
        - **Agent:** Developer
        ## Action Plan
        ### `EXECUTE`
        - **Description:** Echo backticks
        ````shell
        echo 'Here are ``` backticks'
        ````
    """).strip()

    # WHEN
    result = runner.invoke(
        app,
        ["execute", "--plan-content", plan_content, "-y"],
        catch_exceptions=False,
    )

    # THEN
    if result.exit_code != 0:
        print(result.stdout)
    assert result.exit_code == 0
    report = result.stdout

    # The report should contain the output
    assert "Here are ``` backticks" in report

    # AND the surrounding fence must be 4 backticks
    # We look for the pattern: \n````text\n...```\n````
    assert "\n````text\n" in report, "Report did not use quad backticks for fencing"
    assert "\n````\n" in report, "Report did not close with quad backticks"
