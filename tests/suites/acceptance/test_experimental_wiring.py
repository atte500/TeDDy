"""Acceptance tests for the teddy update --experimental flag."""

from typer.testing import CliRunner


def test_experimental_flag_uses_test_pypi_url(monkeypatch):
    """Wiring: `teddy update --experimental` should use TEST_PYPI_URL
    for the version check and show experimental upgrade command."""
    from teddy_executor.__main__ import app
    from teddy_executor.core.services.update_checker import TEST_PYPI_URL

    # Track the index_url passed to fetch_latest_version
    fetch_calls = []

    def tracking_fetch_latest_version(index_url=None, **kwargs):
        fetch_calls.append(index_url)
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

    runner = CliRunner()
    result = runner.invoke(app, ["update", "--experimental"])

    # Exit code 0
    assert result.exit_code == 0, (
        f"Expected exit code 0, got {result.exit_code}. Output: {result.stdout!r}"
    )

    # fetch_latest_version should have been called with TEST_PYPI_URL
    assert len(fetch_calls) >= 1, (
        f"Expected at least 1 call to fetch_latest_version, got {len(fetch_calls)}"
    )
    assert fetch_calls[0] == TEST_PYPI_URL, (
        f"Expected fetch_latest_version with {TEST_PYPI_URL!r}, got {fetch_calls[0]!r}"
    )

    # Output should mention experimental and the pip command with testpypi index
    assert "experimental" in result.stdout.lower(), (
        f"Expected 'experimental' in output, got: {result.stdout!r}"
    )
    assert "0.2.0" in result.stdout, (
        f"Expected version 0.2.0 in output, got: {result.stdout!r}"
    )
    assert "pipx upgrade teddy-cli" in result.stdout
    assert "test.pypi.org" in result.stdout
