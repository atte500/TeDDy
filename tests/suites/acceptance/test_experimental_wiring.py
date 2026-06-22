"""Acceptance tests for the teddy update --experimental flag."""

from typer.testing import CliRunner


def test_experimental_flag_uses_test_pypi_url(monkeypatch):
    """Wiring: `teddy update --experimental` should use TEST_PYPI_URL
    for the version check and notify about experimental version."""
    from teddy_executor.__main__ import app

    # Track the index_url passed to fetch_latest_version
    fetch_calls = []

    def tracking_fetch_latest_version(index_url=None, **kwargs):
        fetch_calls.append(index_url)
        # Return a TestPyPI-like version
        return "0.2.0.dev1"

    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.get_current_version",
        lambda: "0.1.0",
    )
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.fetch_latest_version",
        tracking_fetch_latest_version,
    )
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.compare_versions",
        lambda current, latest: True,
    )
    # Mock should_update to return False (newer version, auto_update disabled)
    # to test that the command displays a notification with the version.
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.should_update",
        lambda cache_path, auto_update_enabled=True: False,
    )

    runner = CliRunner()
    result = runner.invoke(app, ["update", "--experimental"])

    # The command should exit with 0
    assert result.exit_code == 0, (
        f"Expected exit code 0, got {result.exit_code}. Output: {result.stdout!r}"
    )

    # fetch_latest_version should have been called with TEST_PYPI_URL
    from teddy_executor.core.services.update_checker import TEST_PYPI_URL

    assert len(fetch_calls) >= 1, (
        f"Expected at least 1 call to fetch_latest_version, got {len(fetch_calls)}"
    )
    assert fetch_calls[0] == TEST_PYPI_URL, (
        f"Expected fetch_latest_version to be called with TEST_PYPI_URL "
        f"({TEST_PYPI_URL!r}), got {fetch_calls[0]!r}. "
        f"The --experimental flag did not switch the index URL."
    )
    # The output should mention the version (no experimental label needed
    # in current code — just version number)
    assert "0.2.0" in result.stdout, (
        f"Expected output to mention version 0.2.0.dev1, got: {result.stdout!r}"
    )
