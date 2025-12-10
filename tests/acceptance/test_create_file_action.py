import subprocess
import sys
from pathlib import Path


# Path to the teddy executable script
TEDDY_CMD = [sys.executable, "-m", "teddy"]

PLAN_YAML = """
- action: create_file
  params:
    file_path: "{file_path}"
    content: "Hello, World!"
"""


def test_create_file_happy_path(tmp_path: Path):
    """
    Given a YAML plan to create a new file,
    When the user executes the plan,
    Then the file should be created with the correct content.
    """
    # Arrange
    file_name = "new_file.txt"
    new_file_path = tmp_path / file_name
    plan = PLAN_YAML.format(file_path=str(new_file_path))

    # Act
    # We run the command with '-y' to auto-approve the action.
    # The input is piped to stdin.
    # For the walking skeleton, we don't have interactive approval yet.
    # The plan will be executed directly. The `-y` flag will be added later.
    result = subprocess.run(
        TEDDY_CMD,
        input=plan,
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )

    # Assert
    assert result.returncode == 0, f"Teddy failed with stderr: {result.stderr}"
    assert new_file_path.exists(), "The new file was not created."
    assert (
        new_file_path.read_text() == "Hello, World!"
    ), "The file content is incorrect."

    # Verify the report output
    assert "create_file" in result.stdout
    assert "COMPLETED" in result.stdout
    assert str(new_file_path) in result.stdout
