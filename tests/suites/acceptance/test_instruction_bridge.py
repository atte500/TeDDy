from pathlib import Path
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.setup.test_environment import TestEnvironment


def test_resume_with_message_captures_user_request(tmp_path: Path, monkeypatch):
    # Given a session with a pending plan
    (
        TestEnvironment(monkeypatch, tmp_path)
        .setup()
        .with_real_shell()
        .with_real_interactor()
    )
    cli = CliTestAdapter(monkeypatch, tmp_path)

    session_name = "bridge-test"
    turn_dir = tmp_path / ".teddy" / "sessions" / session_name / "01"
    turn_dir.mkdir(parents=True)
    (turn_dir.parent / "session.context").touch()
    (turn_dir / "turn.context").touch()
    (turn_dir / "pathfinder.xml").touch()
    (turn_dir / "meta.yaml").write_text("turn_id: '01'\nagent_name: 'pathfinder'")

    plan_content = MarkdownPlanBuilder("Test Plan").add_execute("echo hello").build()
    (turn_dir / "plan.md").write_text(plan_content, encoding="utf-8")

    # When I resume with a message
    message = "Please focus on performance."
    # -y is auto-approve
    cli.run_cli_command(["resume", session_name, "-m", message, "-y"])

    # Then the execution report MUST include the user request
    report_file = turn_dir / "report.md"
    assert report_file.exists()
    report_content = report_file.read_text()
    assert f"## User Request\n{message}" in report_content
