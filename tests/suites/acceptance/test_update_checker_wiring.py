"""Acceptance tests for the teddy update command (Wiring)."""

from typer.testing import CliRunner


def test_update_command_returns_version_notification_when_newer_version_available(
    monkeypatch,
):
    """Wiring: `teddy update` should display a new version notification.

    Happy path: newer version available, auto_update enabled.
    The command should call the update checker and echo a success message.
    """
    from unittest.mock import Mock
    from teddy_executor.__main__ import app

    # Mock the core update checker functions to return trivial/hardcoded values
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
    # Mock perform_upgrade to simulate a successful upgrade
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.perform_upgrade",
        lambda latest_version, index_url=None: True,
    )

    # Mock the config service to return auto_update=True
    mock_config = Mock()
    mock_config.get_setting.side_effect = lambda key, default=None: (
        True if key == "auto_update" else default
    )

    from teddy_executor.core.ports.outbound.config_service import IConfigService
    import teddy_executor.__main__ as main_module

    original_get_container = main_module.get_container

    def mock_get_container():
        c = original_get_container()
        c.register(IConfigService, instance=mock_config)
        return c

    monkeypatch.setattr(main_module, "get_container", mock_get_container)

    # Mock the project initialization to avoid DI/container wiring
    monkeypatch.setattr(
        "teddy_executor.__main__._ensure_project_initialized",
        lambda container: None,
    )

    runner = CliRunner()
    result = runner.invoke(app, ["update"])

    # The command should exit with 0 and print the new version
    assert result.exit_code == 0, (
        f"Expected exit code 0 for a successful update command, "
        f"got {result.exit_code}. Output: {result.stdout!r}"
    )
    # The output should mention the new version (auto_update=True triggers upgrade message)
    assert "2.0.0" in result.stdout, (
        f"Expected output to contain the new version '2.0.0', "
        f"got stdout: {result.stdout!r}"
    )
    # Since auto_update=True, we should see "Updated to" (the hardcoded success message)
    assert "Updated to" in result.stdout, (
        f"Expected output to contain 'Updated to' since auto_update=True, "
        f"got stdout: {result.stdout!r}"
    )
