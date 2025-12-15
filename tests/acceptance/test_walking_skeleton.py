import subprocess
import sys


def run_teddy(plan: str) -> subprocess.CompletedProcess:
    """Helper function to run the teddy application."""
    # Note: We use sys.executable to ensure we're running the command
    # with the same python that's running the test. This avoids issues
    # with virtual environments. We assume the entry point will be
    # configured as 'teddy' in pyproject.toml.
    process = subprocess.run(
        [sys.executable, "-m", "teddy"],
        input=plan,
        capture_output=True,
        text=True,
        check=False,
    )
    return process


def test_successful_execution():
    """
    Given a valid YAML plan with a single 'echo' command,
    When the plan is piped into the teddy command,
    Then the command should exit with status 0,
    And the report should show SUCCESS with the correct output.
    """
    # GIVEN
    plan_content = """
    - action: execute
      params:
        command: echo "hello world"
    """

    # WHEN
    result = run_teddy(plan_content)

    # THEN
    # The tool itself should run successfully
    assert result.returncode == 0

    # The report should contain the correct elements
    assert "Run Summary: SUCCESS" in result.stdout
    assert "- **Status:** SUCCESS" in result.stdout
    assert "hello world" in result.stdout
    assert "Error:" not in result.stdout


def test_failed_execution():
    """
    Given a valid YAML plan with a failing command,
    When the plan is piped into the teddy command,
    Then the command should exit with status 0 (the tool ran successfully),
    And the report should show FAILURE with the correct error output.
    """
    # GIVEN
    plan_content = """
    - action: execute
      params:
        command: nonexistentcommand12345
    """

    # WHEN
    result = run_teddy(plan_content)

    # THEN
    # The tool should exit with a non-zero code because the plan failed
    assert result.returncode != 0

    # The report should contain the correct failure elements
    assert "Run Summary: FAILURE" in result.stdout
    assert "status: FAILURE" in result.stdout
    assert "error:" in result.stdout
    # The specific shell error message for "command not found"
    assert "not found" in result.stdout or "not recognized" in result.stdout
