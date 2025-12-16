import os
import subprocess
import pytest
import yaml

from textwrap import dedent

# A common place to store the test directory
TEST_DIR = "test_workspace"


@pytest.fixture(autouse=True)
def setup_teardown():
    """Fixture to create and clean up the test directory."""
    if os.path.exists(TEST_DIR):
        subprocess.run(f"rm -rf {TEST_DIR}", shell=True, check=True)
    os.makedirs(TEST_DIR, exist_ok=True)
    yield
    subprocess.run(f"rm -rf {TEST_DIR}", shell=True, check=True)


def run_teddy(plan: str):
    """Helper function to run the teddy CLI with a given plan."""
    plan_path = os.path.join(TEST_DIR, "plan.yml")
    with open(plan_path, "w") as f:
        f.write(plan)

    # Note: We capture stderr and check the return code to ensure we're
    # testing the full end-to-end behavior, including exit codes.
    result = subprocess.run(
        f"poetry run teddy {plan_path}",
        shell=True,
        capture_output=True,
        text=True,
    )
    return result


@pytest.mark.skip(
    reason="This is the acceptance test for Slice 09, which is not yet implemented."
)
def test_edit_action_fails_on_multiple_occurrences():
    # Given a file with content that has multiple occurrences of the find string
    file_path = os.path.join(TEST_DIR, "test.txt")
    original_content = "hello world, hello again"
    with open(file_path, "w") as f:
        f.write(original_content)

    # When an edit action is executed with that find string
    plan = dedent(
        f"""
        actions:
          - action_type: edit
            path: "{file_path}"
            find: "hello"
            replace: "goodbye"
    """
    )
    result = run_teddy(plan)

    # Then the action should fail
    assert result.returncode != 0
    report = yaml.safe_load(result.stdout)
    action_result = report["actions"][0]
    assert action_result["status"] == "FAILURE"
    assert "Multiple occurrences of 'hello' found" in action_result["error"]
    assert action_result["output"] == original_content

    # And the file must remain unchanged
    with open(file_path, "r") as f:
        content_after = f.read()
    assert content_after == original_content
