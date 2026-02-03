from pathlib import Path
from unittest.mock import patch
import yaml
from typer.testing import CliRunner

from teddy_executor.main import app, create_container


def test_execute_markdown_plan_happy_path(tmp_path: Path):
    """
    Given a valid Markdown plan to create a new file,
    When the user executes the plan,
    Then the file should be created with the correct content and the report is valid.
    """
    # Arrange
    runner = CliRunner()
    file_name = "hello.txt"
    new_file_path = tmp_path / file_name

    plan_content = f"""
# Create a test file
- **Status:** Green 🟢
- **Plan Type:** Implementation
- **Agent:** Developer
- **Goal:** Create a simple file.

## Action Plan

### `CREATE`
- **File Path:** [{str(new_file_path)}]({str(new_file_path)})
- **Description:** Create a hello world file.
````text
Hello, world!
````
"""
    plan_file = tmp_path / "plan.md"
    plan_file.write_text(plan_content)

    real_container = create_container()

    # Act
    with patch("teddy_executor.main.container", real_container):
        result = runner.invoke(app, ["execute", str(plan_file), "--yes"])

    # Assert
    assert result.exit_code == 0, (
        f"Teddy failed with stderr: {result.stderr}\\n{result.exception}"
    )
    assert new_file_path.exists(), "The new file was not created."
    assert new_file_path.read_text() == "Hello, world!", (
        "The file content is incorrect."
    )

    # Verify the report output
    report = yaml.safe_load(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"
