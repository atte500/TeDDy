"""Regression test: verify that `teddy update` shows notification with upgrade command.

After the simplification to notification-only updates, the command must:
- Show a notification when a newer version exists
- Display the appropriate upgrade command (pip install --upgrade or uv tool upgrade)
- Not attempt any auto-upgrade
"""

import typer.testing

from teddy_executor.__main__ import app


runner = typer.testing.CliRunner()


def _setup_basic_mocks(monkeypatch):
    """Set up common mocks for update command tests."""
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.get_current_version",
        lambda: "0.1.0",
    )
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.fetch_latest_version",
        lambda index_url=None, **kwargs: "99.99.99",
    )
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.compare_versions",
        lambda current, latest: True,
    )


def test_update_command_shows_notification_for_newer_version(monkeypatch):
    """When a newer version exists, show a notification with upgrade command."""
    _setup_basic_mocks(monkeypatch)

    result = runner.invoke(app, ["update"])

    # Should show notification
    assert "new version" in result.stdout.lower(), (
        f"Expected 'new version' in output, got: {result.stdout!r}"
    )
    # Should contain the uv upgrade command
    assert "uv tool upgrade teddy-cli" in result.stdout, (
        f"Expected uv upgrade command in output, got: {result.stdout!r}"
    )
    # Should not contain upgrade failure or success messages
    assert "failed" not in result.stdout.lower()
    assert "Updated to" not in result.stdout
    # Exit code should be 0
    assert result.exit_code == 0


def test_update_command_shows_notification_for_experimental(monkeypatch):
    """When --experimental flag is used, show experimental upgrade command."""
    _setup_basic_mocks(monkeypatch)

    result = runner.invoke(app, ["update", "--experimental"])

    # Should show experimental notification
    assert "experimental" in result.stdout.lower(), (
        f"Expected 'experimental' in output, got: {result.stdout!r}"
    )
    # Should contain the experimental uv command with testpypi index
    assert "uv tool install teddy-cli" in result.stdout
    assert "test.pypi.org" in result.stdout
    assert result.exit_code == 0


def test_update_command_shows_already_latest_when_no_update(monkeypatch):
    """When no newer version exists, show 'already latest' message."""
    _setup_basic_mocks(monkeypatch)
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.compare_versions",
        lambda current, latest: False,
    )

    result = runner.invoke(app, ["update"])

    assert "already running the latest version" in result.stdout.lower(), (
        f"Expected 'already latest' in output, got: {result.stdout!r}"
    )
    assert result.exit_code == 0


def test_update_command_shows_network_error_when_fetch_fails(monkeypatch):
    """When fetch_latest_version returns None, show network error."""
    _setup_basic_mocks(monkeypatch)
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.fetch_latest_version",
        lambda index_url=None, **kwargs: None,
    )

    result = runner.invoke(app, ["update"])

    assert "network error" in result.stdout.lower(), (
        f"Expected 'network error' in output, got: {result.stdout!r}"
    )
    assert result.exit_code == 0


def test_update_command_hardcoded_upgrade_messages_not_present():
    """Ensure the update function in __main__.py does not contain auto-upgrade logic.
    This safety net catches regression if someone re-adds perform_upgrade or
    prewarm_imports into the update command. Note: these functions are still
    valid for use by other commands (e.g., init), so we only check the update
    function body.
    """
    import inspect
    from teddy_executor.__main__ import update as update_func

    source = inspect.getsource(update_func)
    # The notification-only update function should not contain these
    assert "perform_upgrade" not in source, (
        "perform_upgrade still referenced in update() - auto-upgrade should be removed!"
    )
    assert "prewarm_imports" not in source, (
        "prewarm_imports still referenced in update() - should be removed!"
    )
    # Verify new notification pattern is present
    assert "uv tool upgrade teddy-cli" in source, (
        "Notification uv upgrade command not found in update()"
    )
