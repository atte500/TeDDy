from typer.testing import CliRunner
from teddy_executor.__main__ import app

runner = CliRunner()


def test_resume_auto_detects_latest_session(tmp_path, monkeypatch):
    """
    Given several sessions exist in .teddy/sessions/.
    When I run 'teddy resume' from the project root without arguments.
    Then it MUST automatically pick the most recently modified session.
    """
    monkeypatch.chdir(tmp_path)

    # 1. Create two sessions
    runner.invoke(app, ["start", "older-session"])
    # Wait a second to ensure different timestamps if fs resolution is low
    import time

    time.sleep(1.1)
    runner.invoke(app, ["start", "newer-session"])

    # 2. Run resume from root
    result = runner.invoke(app, ["resume"])

    assert result.exit_code == 0
    # Orchestrator will print "Resuming session: newer-session" or similar
    # We check if it picked the right one
    assert "newer-session" in result.stdout
    assert "older-session" not in result.stdout


def test_resume_with_session_path(tmp_path, monkeypatch):
    """
    Given a session exists.
    When I run 'teddy resume .teddy/sessions/my-session'.
    Then it MUST resolve and resume that session.
    """
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["start", "my-session"])

    result = runner.invoke(app, ["resume", ".teddy/sessions/my-session"])

    assert result.exit_code == 0
    assert "my-session" in result.stdout


def test_resume_with_turn_path(tmp_path, monkeypatch):
    """
    Given a session exists with a turn.
    When I run 'teddy resume .teddy/sessions/my-session/01'.
    Then it MUST resolve the session name and resume it.
    """
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["start", "my-session"])

    result = runner.invoke(app, ["resume", ".teddy/sessions/my-session/01"])

    assert result.exit_code == 0
    assert "my-session" in result.stdout


def test_resume_with_file_path(tmp_path, monkeypatch):
    """
    Given a session exists with a file.
    When I run 'teddy resume .teddy/sessions/my-session/01/meta.yaml'.
    Then it MUST resolve the session name and resume it.
    """
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["start", "my-session"])

    result = runner.invoke(app, ["resume", ".teddy/sessions/my-session/01/meta.yaml"])

    assert result.exit_code == 0
    assert "my-session" in result.stdout
