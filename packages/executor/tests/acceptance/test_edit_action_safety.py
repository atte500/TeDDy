from pathlib import Path
from .helpers import run_teddy_with_plan_structure, parse_yaml_report


def test_edit_action_fails_on_multiple_occurrences(tmp_path: Path):
    # Given a file with content that has multiple occurrences of the find string
    test_dir = tmp_path / "test_project"
    test_dir.mkdir()
    file_to_edit = test_dir / "test.txt"
    original_content = "hello world, hello again"
    file_to_edit.write_text(original_content)

    # When an edit action is executed with that find string
    plan_structure = [
        {
            "action": "edit",
            "params": {
                "file_path": file_to_edit.name,
                "find": "hello",
                "replace": "goodbye",
            },
        }
    ]
    result = run_teddy_with_plan_structure(plan_structure, cwd=test_dir)

    # Then the action should fail
    assert result.returncode != 0

    # The report should indicate failure and the specific reason.
    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "FAILURE"

    action_log = report["action_logs"][0]
    assert action_log["status"] == "FAILURE"
    assert "Aborting edit to prevent ambiguity" in action_log["error"]
    assert action_log["output"] == original_content

    # And the file must remain unchanged
    assert file_to_edit.read_text() == original_content
