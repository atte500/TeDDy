"""Acceptance tests for the teddy update command (Wiring)."""

from typer.testing import CliRunner


def test_update_command_returns_version_notification_when_newer_version_available(
    monkeypatch,
):
    """Wiring: `teddy update` should display a new version notification.

    Happy path: newer version available.
    The command should show a notification and the upgrade command.
    """
    from teddy_executor.__main__ import app

    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.get_current_version",
        lambda: "1.0.0",
    )
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.fetch_latest_version",
        lambda index_url=None, **kwargs: "2.0.0",
    )
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.compare_versions",
        lambda current, latest: True,
    )
    monkeypatch.setattr(
        "teddy_executor.__main__._ensure_project_initialized",
        lambda container: None,
    )

    runner = CliRunner()
    result = runner.invoke(app, ["update"])

    assert result.exit_code == 0, (
        f"Expected exit code 0, got {result.exit_code}. Output: {result.stdout!r}"
    )
    # Should show notification with upgrade command, not auto-upgrade message
    assert "Updated to" not in result.stdout, (
        f"Expected no 'Updated to' in output, got: {result.stdout!r}"
    )
    assert "new version" in result.stdout.lower(), (
        f"Expected 'new version' in output, got: {result.stdout!r}"
    )
    assert "2.0.0" in result.stdout, (
        f"Expected version 2.0.0 in output, got: {result.stdout!r}"
    )
    assert "uv tool upgrade teddy-cli" in result.stdout, (
        f"Expected upgrade command in output, got: {result.stdout!r}"
    )
