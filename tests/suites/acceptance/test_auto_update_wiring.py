"""Acceptance tests: verify update command does not read auto_update config.

After simplification to notification-only, the update command no longer
reads the auto_update config. It always shows a notification when a
newer version is available.
"""


def test_update_command_does_not_read_auto_update_config(monkeypatch):
    """Wiring: `teddy update` should not read auto_update from IConfigService.

    Since the command no longer performs auto-upgrade, it should not read
    the `auto_update` config value. The notification is always shown
    regardless of the config setting.
    """
    from typer.testing import CliRunner
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

    # The command should exit with 0
    assert result.exit_code == 0, (
        f"Expected exit code 0, got {result.exit_code}. Output: {result.stdout!r}"
    )

    # Should show notification
    assert "new version" in result.stdout.lower(), (
        f"Expected 'new version' in output, got: {result.stdout!r}"
    )
    assert "pipx upgrade teddy-cli" in result.stdout, (
        f"Expected upgrade command in output, got: {result.stdout!r}"
    )
    # Should NOT contain --yes (that was for auto-upgrade)
    assert "--yes" not in result.stdout
