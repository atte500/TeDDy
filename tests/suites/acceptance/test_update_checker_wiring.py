"""Acceptance tests for the teddy update command (Wiring)."""

from typer.testing import CliRunner


def test_update_command_returns_version_notification_when_newer_version_available(
    monkeypatch,
):
    """Wiring: `teddy update` should display a new version notification.

    Happy path: newer version available, auto_update enabled.
    The command should call the update checker and echo a success message.
    """
    from teddy_executor.__main__ import app

    # Mock the core update checker functions to return trivial/hardcoded values
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.get_current_version",
        lambda: "1.0.0",
    )
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.fetch_latest_version",
        lambda index_url=None: "2.0.0",
    )
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.compare_versions",
        lambda current, latest: True,
    )

    # Mock the project initialization to avoid DI/container wiring
    monkeypatch.setattr(
        "teddy_executor.__main__._ensure_project_initialized",
        lambda container: None,
    )

    runner = CliRunner()
    result = runner.invoke(app, ["update"])

    # Red phase: command doesn't exist → exit code 2 (no such command)
    assert result.exit_code == 0, (
        f"Expected exit code 0 for a successful update command, "
        f"got {result.exit_code}. stderr: {result.stderr!r}"
    )
    # The output should mention the new version or update success
    assert "2.0.0" in result.stdout, (
        f"Expected output to contain the new version '2.0.0', "
        f"got stdout: {result.stdout!r}"
    )
