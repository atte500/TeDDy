"""Regression test: verify that `teddy update` actually calls perform_upgrade.

On the broken code, `should_update(None)` returns None -> "already latest" branch
is hit, or the success branch prints "Updated to v{latest}" without calling
perform_upgrade. This test ensures that when auto_update=True and a newer version
exists, the upgrade is performed and success is conditional on the result.
"""

import typer.testing

from teddy_executor.__main__ import app
from teddy_executor.core.services.update_checker import PYPI_URL


runner = typer.testing.CliRunner()


class _MockConfigService:
    """A simple config service mock that returns configurable values."""

    def __init__(self, auto_update: bool = True):
        self._auto_update = auto_update

    def get_setting(self, key: str, default=None):
        if key == "auto_update":
            return self._auto_update
        return default


def _mock_container(monkeypatch, auto_update: bool):
    """Sets up monkeypatches for the DI container and config service.

    Returns tracking helpers for perform_upgrade and prewarm_imports calls.
    """
    # Tracking containers (plain lists to avoid any mock library)
    perform_upgrade_calls = []
    prewarm_calls = []

    config_service = _MockConfigService(auto_update=auto_update)

    def mock_resolve(*args, **kwargs):
        return config_service

    def mock_get_container():
        # Return a simple object with a resolve method (and register no-op)
        container = type(
            "Container",
            (),
            {"resolve": mock_resolve, "register": lambda *a, **kw: None},
        )()
        return container

    monkeypatch.setattr("teddy_executor.__main__.get_container", mock_get_container)

    def track_perform_upgrade(latest_version, index_url=PYPI_URL):
        perform_upgrade_calls.append((latest_version, index_url))
        return True  # default success

    def track_prewarm():
        prewarm_calls.append(True)

    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.fetch_latest_version",
        lambda index_url=None: "99.99.99",
    )
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.get_current_version",
        lambda: "0.1.0",
    )
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.compare_versions",
        lambda current, latest: True,
    )
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.perform_upgrade",
        track_perform_upgrade,
    )
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.cli_helpers.prewarm_imports",
        track_prewarm,
    )

    return perform_upgrade_calls, prewarm_calls


def _mock_container_upgrade_fails(monkeypatch):
    """Like _mock_container but returns False from perform_upgrade."""
    perform_upgrade_calls = []
    prewarm_calls = []

    config_service = _MockConfigService(auto_update=True)

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
        "teddy_executor.core.services.update_checker.fetch_latest_version",
        lambda index_url=None: "99.99.99",
    )
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.get_current_version",
        lambda: "0.1.0",
    )
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.compare_versions",
        lambda current, latest: True,
    )

    def track_perform_upgrade_fail(latest_version, index_url=PYPI_URL):
        perform_upgrade_calls.append((latest_version, index_url))
        return False

    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.perform_upgrade",
        track_perform_upgrade_fail,
    )

    def track_prewarm():
        prewarm_calls.append(True)

    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.cli_helpers.prewarm_imports",
        track_prewarm,
    )

    return perform_upgrade_calls, prewarm_calls


def test_update_command_calls_perform_upgrade_when_auto_update_true(monkeypatch):
    """When auto_update=True and a newer version exists,
    perform_upgrade must be called and success message conditional."""
    perform_upgrade_calls, prewarm_calls = _mock_container(
        monkeypatch, auto_update=True
    )

    result = runner.invoke(app, ["update"])

    # 1. It must have called perform_upgrade with the correct args
    assert len(perform_upgrade_calls) == 1, (
        f"Expected 1 call to perform_upgrade, got {len(perform_upgrade_calls)}"
    )
    assert perform_upgrade_calls[0] == ("99.99.99", PYPI_URL), (
        f"Expected call with ('99.99.99', PYPI_URL), got {perform_upgrade_calls[0]}"
    )

    # 2. It must print success (because upgrade returned True)
    assert "Updated to v99.99.99." in result.stdout

    # 3. prewarm_imports must be called after success
    assert len(prewarm_calls) == 1, (
        f"Expected 1 call to prewarm_imports, got {len(prewarm_calls)}"
    )

    # 4. Exit code should be 0 (success)
    assert result.exit_code == 0


def test_update_command_shows_error_when_upgrade_fails(monkeypatch):
    """When perform_upgrade returns False, an error should be shown."""
    perform_upgrade_calls, prewarm_calls = _mock_container_upgrade_fails(monkeypatch)

    result = runner.invoke(app, ["update"])

    # Must have called perform_upgrade
    assert len(perform_upgrade_calls) == 1, (
        f"Expected 1 call to perform_upgrade, got {len(perform_upgrade_calls)}"
    )
    assert perform_upgrade_calls[0] == ("99.99.99", PYPI_URL), (
        f"Expected call with ('99.99.99', PYPI_URL), got {perform_upgrade_calls[0]}"
    )

    # Error message must be shown
    assert "failed" in result.stdout.lower()
    assert "error" in result.stdout.lower()

    # Exit code should be 1 (failure)
    assert result.exit_code == 1

    # prewarm_imports must NOT be called on failure
    assert len(prewarm_calls) == 0, (
        f"Expected 0 calls to prewarm_imports, got {len(prewarm_calls)}"
    )


def test_update_command_notifies_when_auto_update_false(monkeypatch):
    """When auto_update=False and --yes not given, show notification."""
    # Use _mock_container with auto_update=False, but override perform_upgrade
    # to track it should NOT be called.
    perform_upgrade_calls = []

    config_service = _MockConfigService(auto_update=False)

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
        "teddy_executor.core.services.update_checker.fetch_latest_version",
        lambda index_url=None: "99.99.99",
    )
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.get_current_version",
        lambda: "0.1.0",
    )
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.compare_versions",
        lambda current, latest: True,
    )

    # Track that perform_upgrade is NOT called
    def track_perform_upgrade_never(latest_version, index_url=PYPI_URL):
        perform_upgrade_calls.append((latest_version, index_url))
        return True

    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.perform_upgrade",
        track_perform_upgrade_never,
    )

    result = runner.invoke(app, ["update"])

    # Must NOT call perform_upgrade
    assert len(perform_upgrade_calls) == 0, (
        f"Expected 0 calls to perform_upgrade, got {len(perform_upgrade_calls)}"
    )

    # Must show notification to run --yes
    assert "new version" in result.stdout.lower()
    assert "--yes" in result.stdout

    # Exit code should be 0 (no error, just info)
    assert result.exit_code == 0


def test_update_command_hardcoded_success_not_present():
    """Ensure the hardcoded success branch (without perform_upgrade) no longer exists.
    This is a safety net: if the code is refactored and the hardcoded branch reappears,
    this test will catch it.
    """
    from pathlib import Path

    source = (
        Path(__file__).parents[3] / "src" / "teddy_executor" / "__main__.py"
    ).read_text(encoding="utf-8")
    assert "Hardcoded" not in source, (
        "Hardcoded success comment still present - fix missing!"
    )
    assert "perform_upgrade" in source, "perform_upgrade call missing from __main__.py"
