from pathlib import Path
import yaml
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

    plan = CREATE_PLAN_YAML.format(file_path=existing_file.as_posix())

    # Act
    result = run_teddy_with_stdin(plan, cwd=tmp_path)

    # Assert
    # The tool should exit with a failure code because the plan failed
    assert result.returncode != 0, (
        "Teddy should exit with a non-zero code on plan failure"
    )

    # The original file should not have been modified
    assert existing_file.read_text() == original_content

    # The report should clearly indicate the failure and include the original content
    report = yaml.safe_load(result.stdout)
    assert report["run_summary"]["status"] == "FAILURE"

    action_log = report["action_logs"][0]
    assert action_log["status"] == "FAILURE"
    assert "File exists" in action_log["error"]
    assert action_log["output"] == original_content
