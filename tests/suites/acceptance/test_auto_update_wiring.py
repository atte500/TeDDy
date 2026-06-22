"""Acceptance tests for auto_update config wiring."""

from unittest.mock import Mock


def test_update_command_reads_auto_update_from_config(monkeypatch):
    """Wiring: `teddy update` should read auto_update from IConfigService.

    When auto_update is false in config, should_update should be called
    with auto_update_enabled=False, resulting in a notification-only message.
    """
    from typer.testing import CliRunner
    from teddy_executor.__main__ import app

    # Track the auto_update_enabled argument passed to should_update
    should_update_calls = []

    def tracking_should_update(cache_path, auto_update_enabled=True):
        should_update_calls.append(auto_update_enabled)
        return False  # Simulate notification-only behavior (newer version, but no auto-update)

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
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.should_update",
        tracking_should_update,
    )
    monkeypatch.setattr(
        "teddy_executor.__main__._ensure_project_initialized",
        lambda container: None,
    )

    # Mock IConfigService to return False for auto_update
    mock_config = Mock()
    mock_config.get_setting.side_effect = lambda key, default=None: (
        False if key == "auto_update" else default
    )

    # Monkeypatch the container to provide our mock config service
    from teddy_executor.core.ports.outbound.config_service import IConfigService
    import teddy_executor.container as container_module

    original_get_container = container_module.get_container

    def mock_get_container():
        c = original_get_container()
        c.register(IConfigService, instance=mock_config)
        return c

    monkeypatch.setattr(container_module, "get_container", mock_get_container)

    runner = CliRunner()
    result = runner.invoke(app, ["update"])

    # The command should exit with 0
    assert result.exit_code == 0, (
        f"Expected exit code 0, got {result.exit_code}. Output: {result.stdout!r}"
    )

    # should_update should have been called with auto_update_enabled=False
    assert len(should_update_calls) >= 1, (
        f"Expected at least 1 call to should_update, got {len(should_update_calls)}"
    )
    assert should_update_calls[0] is False, (
        f"Expected should_update to be called with auto_update_enabled=False, "
        f"got {should_update_calls[0]}. The hardcoded auto_update=True was not replaced."
    )
    # The output should contain a notification message (not an update success)
    assert "2.0.0" in result.stdout, (
        f"Expected output to mention version 2.0.0, got: {result.stdout!r}"
    )
