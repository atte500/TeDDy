"""Acceptance tests for the teddy update --experimental flag.

Regression coverage for the stale-index bug: dev pre-releases are published to
PyPI (see .github/workflows/publish.yml), so --experimental must check PyPI
(including pre-releases) rather than the retired, now-frozen TestPyPI index.
"""

import json
import urllib.request

from typer.testing import CliRunner

from teddy_executor.__main__ import app
from teddy_executor.core.services.update_checker import PYPI_URL
from tests.harness.setup.fake_http_response import FakeHTTPResponse


def test_experimental_flag_uses_pypi_url(monkeypatch):
    """Wiring: --experimental checks PyPI, not the retired TestPyPI index."""
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

    result = CliRunner().invoke(app, ["update", "--experimental"])

    assert result.exit_code == 0, (
        f"Expected exit code 0, got {result.exit_code}. Output: {result.stdout!r}"
    )
    assert len(fetch_calls) >= 1, (
        f"Expected at least 1 call to fetch_latest_version, got {len(fetch_calls)}"
    )
    assert fetch_calls[0] == PYPI_URL, (
        f"Expected fetch_latest_version with {PYPI_URL!r}, got {fetch_calls[0]!r}"
    )
    assert "experimental" in result.stdout.lower(), (
        f"Expected 'experimental' in output, got: {result.stdout!r}"
    )
    assert "0.2.0" in result.stdout, (
        f"Expected version 0.2.0 in output, got: {result.stdout!r}"
    )
    assert "uv tool install teddy-cli --pre --force" in result.stdout


def test_experimental_reports_newest_dev_release_from_pypi(monkeypatch):
    """Behavioural regression: --experimental reports the newest dev release on
    PyPI, not the frozen TestPyPI ceiling.

    Frozen TestPyPI tops out at 0.1.16.dev1148; PyPI carries 0.1.17.dev1198.
    """
    pypi_payload = {
        "info": {"version": "0.1.16"},
        "releases": {"0.1.16": [], "0.1.17.dev1198": []},
    }
    testpypi_payload = {
        "info": {"version": "0.1.16.dev1148"},
        "releases": {"0.1.15.dev900": [], "0.1.16.dev1148": []},
    }

    def mock_urlopen(req, *args, **kwargs):
        url = getattr(req, "full_url", str(req))
        payload = testpypi_payload if "test.pypi.org" in url else pypi_payload
        return FakeHTTPResponse(data=json.dumps(payload), status_code=200)

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.get_current_version",
        lambda: "0.1.16.dev1148",
    )

    result = CliRunner().invoke(app, ["update", "--experimental"])

    assert result.exit_code == 0, (
        f"Expected exit code 0, got {result.exit_code}. Output: {result.stdout!r}"
    )
    assert "0.1.17.dev1198" in result.stdout, (
        f"Expected newest PyPI dev release in output, got: {result.stdout!r}"
    )
