"""Acceptance tests for experimental flag and dev-version update behavior.

Covers:
- Experimental flag should fetch dev releases from TestPyPI (not return None).
- When current version is a pre-release and latest is stable, should offer upgrade.
- Notification-only behavior (no auto-upgrade).
"""

import typer.testing

from teddy_executor.__main__ import app


runner = typer.testing.CliRunner()


def _setup_basic_mocks(monkeypatch):
    """Helper to set up common monkeypatches for update command tests."""
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.get_current_version",
        lambda: "0.1.0",
    )


def _setup_fetch_latest_mock(monkeypatch, return_value):
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.fetch_latest_version",
        lambda index_url=None, stable_only=True: return_value,
    )


def _setup_compare_versions_mock(monkeypatch, return_value):
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.compare_versions",
        lambda current, latest: return_value,
    )


def test_experimental_flag_uses_stable_only_false(monkeypatch):
    """When --experimental is used, fetch_latest_version should be called
    with stable_only=False (to include dev releases from TestPyPI)."""
    import teddy_executor.core.services.update_checker as uc

    _setup_basic_mocks(monkeypatch)
    _setup_compare_versions_mock(monkeypatch, True)

    called_with = {}

    def tracking_fetch(index_url=None, stable_only=True):
        called_with["stable_only"] = stable_only
        return "99.99.99"

    monkeypatch.setattr(
        uc, "fetch_latest_version", tracking_fetch
    )

    runner.invoke(app, ["update", "--experimental"])

    assert called_with.get("stable_only") is False, (
        f"Expected stable_only=False for experimental flag, got {called_with.get('stable_only')}"
    )


def test_dev_version_offers_upgrade_to_stable(monkeypatch):
    """When current version is a pre-release and latest is stable,
    the update notification should be offered even though PEP 440 says dev > stable."""
    _setup_basic_mocks(monkeypatch)

    # compare_versions returns False (dev > stable in PEP 440)
    _setup_compare_versions_mock(monkeypatch, False)

    def mock_is_prerelease(version_str):
        if version_str == "0.1.5.dev646":
            return True
        return False

    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.is_prerelease",
        mock_is_prerelease,
    )
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.get_current_version",
        lambda: "0.1.5.dev646",
    )
    _setup_fetch_latest_mock(monkeypatch, "0.1.4")

    result = runner.invoke(app, ["update"])

    # Should show notification with upgrade command
    assert "new version" in result.stdout.lower(), (
        f"Expected 'new version' in output, got: {result.stdout!r}"
    )
    assert "0.1.4" in result.stdout, (
        f"Expected version 0.1.4 in output, got: {result.stdout!r}"
    )
    assert "pip install --upgrade teddy-cli" in result.stdout, (
        f"Expected upgrade command in output, got: {result.stdout!r}"
    )
    assert result.exit_code == 0


def test_dev_version_notifies_without_auto_upgrade(monkeypatch):
    """When current is prerelease and latest is stable, the command shows
    notification without attempting auto-upgrade."""
    _setup_basic_mocks(monkeypatch)
    _setup_compare_versions_mock(monkeypatch, False)

    def mock_is_prerelease(version_str):
        if version_str == "0.1.5.dev646":
            return True
        return False

    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.is_prerelease",
        mock_is_prerelease,
    )
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.get_current_version",
        lambda: "0.1.5.dev646",
    )
    _setup_fetch_latest_mock(monkeypatch, "0.1.4")

    result = runner.invoke(app, ["update"])

    # Must NOT contain "Updated to" (no auto-upgrade)
    assert "Updated to" not in result.stdout, (
        f"Expected no 'Updated to' message, got: {result.stdout!r}"
    )
    # Must show notification
    assert "new version" in result.stdout.lower(), (
        f"Expected notification in output, got: {result.stdout!r}"
    )
    assert result.exit_code == 0
