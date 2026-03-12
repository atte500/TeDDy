from typer.testing import CliRunner
from teddy_executor.__main__ import app

runner = CliRunner()


def test_resume_picks_up_pending_execution(tmp_path, monkeypatch):
    """
    Scenario: Resume picks up pending execution
    Given a turn directory with plan.md but no report.md.
    When I run teddy resume.
    Then it MUST automatically start the execution/approval flow for that plan.
    """
    # Arrange: Setup a session with a pending plan
    session_name = "test-resume-pending"
    session_dir = tmp_path / ".teddy" / "sessions" / session_name
    turn_dir = session_dir / "01"
    turn_dir.mkdir(parents=True)

    plan_content = """# Plan: Test
- Status: Green
- Plan Type: GREEN Phase
- Agent: Developer

## Rationale
``````
Test
``````

## Action Plan
### `CREATE`
- **File Path:** [foo.txt](foo.txt)
- **Description:** Create foo
````text
hello
````
"""
    (turn_dir / "plan.md").write_text(plan_content)
    (turn_dir / "meta.yaml").write_text("turn_id: '01'")
    (turn_dir / "turn.context").write_text("foo.txt")
    (session_dir / "session.context").write_text("")
    (turn_dir / "system_prompt.xml").write_text("<prompt>test</prompt>")

    # Mock working directory to be inside the session
    monkeypatch.chdir(tmp_path)

    # Act: Run teddy resume
    result = runner.invoke(app, ["resume", session_name, "--no-interactive"])

    # Assert
    assert result.exit_code == 0
    # Side effects are the most reliable way to verify execution in acceptance tests
    assert (tmp_path / "foo.txt").exists()
    assert (turn_dir / "report.md").exists()

    # Check that the report confirms success
    report_content = (turn_dir / "report.md").read_text()
    assert "**Overall Status:** SUCCESS" in report_content
