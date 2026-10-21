"""Unit invariants: ``teddy init`` performs no interactive setup.

The acceptance module proves the negative scenario end to end. This module pins
the seam so a future edit cannot silently reintroduce the prompt: the init-only
gate helper is gone, and neither ``teddy init`` nor ``teddy init config`` reaches
the session-start setup gates even when a terminal is attached.
"""

import pytest

from teddy_executor import __main__ as cli_entry
from teddy_executor.adapters.inbound import session_cli_handlers

from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.setup.test_environment import TestEnvironment


def _spy_on_setup_gates(monkeypatch) -> list[str]:
    """Record which session-start setup gates an init command invokes, in order."""
    calls: list[str] = []
    monkeypatch.setattr(
        session_cli_handlers,
        "_ensure_api_key_configured",
        lambda config_service, setup_api_key: calls.append("api_key"),
    )
    monkeypatch.setattr(
        session_cli_handlers,
        "_validate_editor_config",
        lambda container: calls.append("editor"),
    )
    return calls


def test_init_only_setup_gate_helper_is_removed():
    """The init-only gate helper is deleted so no init call site can prompt again."""
    assert not hasattr(cli_entry, "_run_init_setup_gates")


@pytest.mark.parametrize("args", [["init"], ["init", "config"]])
def test_init_commands_never_run_session_setup_gates(tmp_path, monkeypatch, args):
    """A TTY init command must not reach the session-start setup gates."""
    TestEnvironment(monkeypatch, tmp_path).setup().with_tty(True)
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    calls = _spy_on_setup_gates(monkeypatch)

    result = adapter.run_command(args)

    assert result.exit_code == 0, result.stdout + result.stderr
    assert calls == [], f"'{' '.join(args)}' must not run the session setup gates"
