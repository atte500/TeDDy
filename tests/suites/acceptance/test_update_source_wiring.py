"""Acceptance coverage for the configurable update source.

With ``update.index_url`` configured, both entry points must query that
endpoint; the default configuration must keep reaching the official PyPI
endpoint. The container is injected through the module seam so no test depends
on the developer's live ``.teddy/config.yaml``.
"""

from typer.testing import CliRunner

from teddy_executor.core.services.update_checker import PYPI_URL
from tests.harness.setup.update_source import (
    container_with_config,
    write_update_config,
)

CUSTOM_URL = "https://example.test/pypi/teddy-cli/json"


def _track_fetches(monkeypatch) -> list[str]:
    """Record every index URL that reaches the network fetch."""
    calls: list[str] = []

    def tracking_fetch(index_url=None, **kwargs):
        calls.append(index_url)
        return "2.0.0"

    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.fetch_latest_version",
        tracking_fetch,
    )
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.get_current_version",
        lambda: "1.0.0",
    )
    monkeypatch.setattr(
        "teddy_executor.core.services.update_checker.compare_versions",
        lambda current, latest: True,
    )
    return calls


def test_update_command_queries_the_configured_source(tmp_path, monkeypatch):
    """A configured `update.index_url` becomes the URL `teddy update` fetches."""
    from teddy_executor.__main__ import app

    calls = _track_fetches(monkeypatch)
    config_path = write_update_config(tmp_path, CUSTOM_URL)
    container = container_with_config(config_path)
    monkeypatch.setattr("teddy_executor.__main__.get_container", lambda: container)

    result = CliRunner().invoke(app, ["update"])

    assert result.exit_code == 0, result.stdout
    assert calls == [CUSTOM_URL]
    assert "2.0.0" in result.stdout


def test_update_command_uses_the_official_endpoint_by_default(tmp_path, monkeypatch):
    """Without a user config, `teddy update` keeps querying the official endpoint."""
    from teddy_executor.__main__ import app

    calls = _track_fetches(monkeypatch)
    container = container_with_config(tmp_path / ".teddy" / "config.yaml")
    monkeypatch.setattr("teddy_executor.__main__.get_container", lambda: container)

    result = CliRunner().invoke(app, ["update"])

    assert result.exit_code == 0, result.stdout
    assert calls == [PYPI_URL]


def test_background_check_receives_the_configured_source(tmp_path, monkeypatch):
    """The startup daemon thread is handed the resolved source, not a bare default."""
    from teddy_executor.adapters.inbound import session_cli_handlers as handlers

    config_path = write_update_config(tmp_path, CUSTOM_URL)
    container = container_with_config(config_path)
    recorded: list[tuple] = []

    class RecordingThread:
        def __init__(self, *, target, args=(), daemon=False, **kwargs):
            recorded.append((target, args, daemon))

        def start(self) -> None:
            pass

    monkeypatch.setattr("threading.Thread", RecordingThread)

    handlers._start_background_update_check(container)

    assert len(recorded) == 1
    target, args, daemon = recorded[0]
    assert target is handlers.background_check
    assert daemon is True
    assert args[0].name == ".update_cache.json"
    assert args[1] == CUSTOM_URL
