"""Acceptance tests for auto_update config wiring."""

from unittest.mock import Mock


def test_update_command_reads_auto_update_from_config(monkeypatch):
    """Wiring: `teddy update` should read auto_update from IConfigService.

    When auto_update is false in config, the command should show a notification
    rather than auto-upgrading. Verifies the config is read and respected.
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

    # Config service should have been called to read auto_update
    mock_config.get_setting.assert_called_with("auto_update", default=True)

    # Should show notification, not auto-upgrade
    assert "new version" in result.stdout.lower()
    assert "--yes" in result.stdout
    assert "2.0.0" in result.stdout, (
        f"Expected output to mention version 2.0.0, got: {result.stdout!r}"
    )
