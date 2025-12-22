from pathlib import Path
from .helpers import run_teddy_with_stdin

CREATE_PLAN_YAML = """
- action: create_file
  params:
    file_path: "{file_path}"
    content: "This is new content."
"""


def test_create_file_on_existing_file_fails_and_returns_content(tmp_path: Path):
    """
    Given a file that already exists,
    When a plan is executed to create the same file,
    Then the action should fail, the original file should be unchanged,
    and the report's output should contain the original content of the file.
    """
    # Arrange
    existing_file = tmp_path / "existing.txt"
    original_content = "original content"
    existing_file.write_text(original_content)

    plan = CREATE_PLAN_YAML.format(file_path=str(existing_file))

    # Act
    result = run_teddy_with_stdin(plan, cwd=tmp_path)

    # Assert
    # The tool should exit with a failure code because the plan failed
    assert (
        result.returncode != 0
    ), "Teddy should exit with a non-zero code on plan failure"

    # The original file should not have been modified
    assert existing_file.read_text() == original_content

    # The report should clearly indicate the failure and include the original content
    assert "status: FAILURE" in result.stdout
    assert "error: File exists:" in result.stdout
    assert "output: |" in result.stdout
    assert f"    {original_content}" in result.stdout
