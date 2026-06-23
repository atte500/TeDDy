"""Acceptance tests for experimental flag and dev-version update behavior.

Covers:
- Experimental flag should fetch dev releases from TestPyPI (not return None).
- When current version is a pre-release and latest is stable, should offer upgrade.
"""

import typer.testing

from teddy_executor.__main__ import app


runner = typer.testing.CliRunner()


class _MockConfigService:
    def __init__(self, auto_update=True):
        self._auto_update = auto_update
    def get_setting(self, key, default=None):
        if key == "auto_update":
            return self._auto_update
        return default


def _setup_basic_mocks(monkeypatch, auto_update=True):
    """Helper to set up the common monkeypatches for update command tests."""
    config_service = _MockConfigService(auto_update=auto_update)

    def mock_resolve(*args, **kwargs):
        return config_service

    def mock_get_container():
        container = type(
            "Container",
            (),
            {"resolve": mock_resolve, "register": lambda *a, **kw: None},
        )()
        return container

    monkeypatch.setattr("teddy_executor.__main__.get_container", mock_get_container)
    monkeypatch.setattr(
        "teddy_executor.__main__._ensure_project_initialized",
        lambda container: None,
    )
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.get_current_version",
        lambda: "0.1.0",
    )


def _setup_fetch_latest_mock(monkeypatch, return_value):
    """Helper to mock fetch_latest_version."""
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

    # Track the stable_only argument
    called_with = {}

    def tracking_fetch(index_url=None, stable_only=True):
        called_with["stable_only"] = stable_only
        return "99.99.99"

    monkeypatch.setattr(
        uc, "fetch_latest_version", tracking_fetch
    )

    # Also mock perform_upgrade to avoid actual installation
    monkeypatch.setattr(
        uc, "perform_upgrade", lambda latest_version, index_url=None: True
    )
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.cli_helpers.prewarm_imports",
        lambda: None,
    )

    runner.invoke(app, ["update", "--experimental"])

    assert called_with.get("stable_only") is False, (
        f"Expected stable_only=False for experimental flag, got {called_with.get('stable_only')}"
    )


def test_dev_version_offers_upgrade_to_stable(monkeypatch):
    """When current version is a pre-release (e.g., 0.1.5.dev646) and latest
    is a stable release (e.g., 0.1.4), the update should be offered even though
    PEP 440 says dev > stable."""
    _setup_basic_mocks(monkeypatch, auto_update=True)

    # Ensure compare_versions returns False (dev > stable)
    _setup_compare_versions_mock(monkeypatch, False)

    # Mock is_prerelease to simulate current as prerelease, latest as stable
    def mock_is_prerelease(version_str):
        if version_str == "0.1.5.dev646":
            return True
        return False

    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.is_prerelease",
        mock_is_prerelease,
    )
    # Mock get_current_version to return a dev string
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.get_current_version",
        lambda: "0.1.5.dev646",
    )
    _setup_fetch_latest_mock(monkeypatch, "0.1.4")

    # Track that perform_upgrade IS called
    calls = []
    def track_upgrade(latest_version, index_url=None):
        calls.append(latest_version)
        return True

    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.perform_upgrade",
        track_upgrade,
    )
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.cli_helpers.prewarm_imports",
        lambda: None,
    )

    result = runner.invoke(app, ["update"])

    # Should have called perform_upgrade (the upgrade should proceed)
    assert len(calls) == 1, f"Expected perform_upgrade to be called, got {len(calls)}"
    assert "Updated to v0.1.4." in result.stdout


def test_dev_version_notifies_when_auto_update_false(monkeypatch):
    """When current is prerelease, latest is stable, but auto_update=False,
    should show notification with --yes hint."""
    _setup_basic_mocks(monkeypatch, auto_update=False)
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

    # Track that perform_upgrade is NOT called
    calls = []
    def track_upgrade(latest_version, index_url=None):
        calls.append(latest_version)
        return True

    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.perform_upgrade",
        track_upgrade,
    )

    result = runner.invoke(app, ["update"])

    assert len(calls) == 0, (
        f"Expected perform_upgrade NOT to be called, got {len(calls)}"
    )
    assert "new version" in result.stdout.lower()
    assert "--yes" in result.stdout
    assert "0.1.4" in result.stdout