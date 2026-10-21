"""Unit coverage for the init drift-advice seam (Slice 00-39).

The acceptance tracer bullet (``tests/suites/acceptance/test_init_drift_reporting.py``)
proves bare ``teddy init`` prints the drift advice end to end. This file pins the
seam itself, so a refactor cannot silently detach the advice:

* bare ``teddy init`` invokes ``_display_init_drift`` exactly once, AFTER the
  ``TeDDy initialized ...`` summary echo;
* the advice is NOT TTY-gated (unlike the setup gates), so it fires both on and
  off a TTY;
* the destructive subcommands (``init prompts`` / ``init templates``) never
  invoke it, because ``init_callback`` returns before the call for them.
"""

import pytest
import typer

from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.setup.test_environment import TestEnvironment


_DRIFT_MARKER = "DRIFT_ADVICE_MARKER"


def _spy_on_drift(monkeypatch) -> list:
    """Replace ``_display_init_drift`` with a recording, marker-emitting spy.

    The spy echoes a unique marker so the caller can assert the advice prints
    AFTER the summary echo.
    """
    calls: list = []

    def _spy(container):
        calls.append(container)
        typer.echo(_DRIFT_MARKER)

    monkeypatch.setattr("teddy_executor.__main__._display_init_drift", _spy)
    return calls


@pytest.mark.parametrize("tty", [False, True])
def test_bare_init_invokes_drift_after_summary(tmp_path, monkeypatch, tty):
    """Bare ``teddy init`` calls the drift advice once, after the summary echo."""
    TestEnvironment(monkeypatch, tmp_path).setup().with_tty(tty)
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    calls = _spy_on_drift(monkeypatch)

    result = adapter.run_command(["init"])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert len(calls) == 1, "bare init must invoke the drift advice exactly once"
    stdout = result.stdout
    assert "TeDDy initialized" in stdout, stdout
    assert stdout.index("TeDDy initialized") < stdout.index(_DRIFT_MARKER), (
        "the drift advice must print AFTER the summary echo"
    )


@pytest.mark.parametrize("subcommand", ["prompts", "templates"])
def test_destructive_subcommands_do_not_invoke_drift(tmp_path, monkeypatch, subcommand):
    """``teddy init prompts`` / ``init templates`` never emit the drift advice."""
    TestEnvironment(monkeypatch, tmp_path).setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    calls = _spy_on_drift(monkeypatch)

    result = adapter.run_command(["init", subcommand])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert calls == [], f"'init {subcommand}' must not invoke the drift advice"
    assert _DRIFT_MARKER not in (result.stdout + result.stderr)
