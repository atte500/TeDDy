import subprocess
import sys
import textwrap
from pathlib import Path


# Path to the teddy executable script
TEDDY_CMD = [sys.executable, "-m", "teddy"]


def run_teddy(plan: str, cwd: Path) -> subprocess.CompletedProcess:
    """Helper function to run teddy with a given plan."""
    return subprocess.run(
        TEDDY_CMD,
        input=plan,
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def test_edit_action_fails_on_multiple_occurrences(tmp_path: Path):
    # Given a file with content that has multiple occurrences of the find string
    test_dir = tmp_path / "test_project"
    test_dir.mkdir()
    file_to_edit = test_dir / "test.txt"
    original_content = "hello world, hello again"
    file_to_edit.write_text(original_content)

    # When an edit action is executed with that find string
    plan = textwrap.dedent(
        f"""
        - action: edit
          params:
            file_path: "{file_to_edit.name}"
            find: "hello"
            replace: "goodbye"
    """
    )
    result = run_teddy(plan, cwd=test_dir)

    # Then the action should fail
    assert result.returncode != 0

    # The report should indicate failure and the specific reason.
    assert "Run Summary: FAILURE" in result.stdout
    assert "status: FAILURE" in result.stdout
    assert "Aborting edit to prevent ambiguity" in result.stdout
    assert "output: |" in result.stdout
    assert f"    {original_content}" in result.stdout

    # And the file must remain unchanged
    assert file_to_edit.read_text() == original_content
