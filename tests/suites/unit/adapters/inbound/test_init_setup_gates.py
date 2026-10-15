"""Unit coverage for the init-time interactive setup gates (Slice 00-37).

The acceptance tracer bullet (``tests/suites/acceptance/test_init_interactive_setup.py``)
proves bare ``teddy init`` persists a missing API key on a TTY. This file fills
the remaining init-time prompt matrix, driving the ``_run_init_setup_gates`` seam
and the ``teddy init`` / ``teddy init config`` commands through the harness:

* a non-TTY ``init`` prompts for NEITHER the API key nor the editor (the gates
  return early, so automated / CI runs stay clean);
* on a TTY the gates run in the preflight order (API key, then editor);
* a TTY ``init`` prompts for the editor when none is configured, reusing the
  preflight ``_validate_editor_config`` gate (no new prompt logic);
* ``teddy init config`` re-runs the gates after its overwrite, so the reset
  editor re-prompts.
"""

from teddy_executor.__main__ import _run_init_setup_gates
from teddy_executor.adapters.inbound import session_cli_handlers
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment

from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.setup.test_environment import TestEnvironment


def _configure(env, *, api_key: str, editor: str):
    """Drive the mocked ``IConfigService`` to a given key/editor state."""
    mock_config = env.get_service(IConfigService)
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "llm.api_key": api_key,
        "editor": editor,
    }.get(key, default)
    return mock_config


def _discover_nvim(env) -> None:
    """Make editor discovery resolve a single ``nvim`` candidate."""
    mock_env = env.get_service(ISystemEnvironment)
    mock_env.which.side_effect = lambda name: (
        "/usr/bin/nvim" if name == "nvim" else None
    )


def _spy_on_gates(monkeypatch) -> list:
    """Record which setup gates ``_run_init_setup_gates`` invokes, in order."""
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


def test_run_init_setup_gates_skips_both_gates_when_not_a_tty(tmp_path, monkeypatch):
    """A non-TTY run returns early: neither the API-key nor the editor gate runs."""
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_tty(False)
    calls = _spy_on_gates(monkeypatch)

    _run_init_setup_gates(env.container)

    assert calls == []


def test_run_init_setup_gates_runs_api_key_before_editor_on_tty(tmp_path, monkeypatch):
    """On a TTY the gates run in preflight order: API key, then editor."""
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_tty(True)
    calls = _spy_on_gates(monkeypatch)

    _run_init_setup_gates(env.container)

    assert calls == ["api_key", "editor"]


def test_bare_init_on_tty_prompts_for_unconfigured_editor(tmp_path, monkeypatch):
    """``teddy init`` on a TTY discovers and persists an editor when unconfigured."""
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_tty(True)
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    mock_config = _configure(env, api_key="sk-present", editor="")
    _discover_nvim(env)
    monkeypatch.setattr("typer.prompt", lambda *a, **k: "1")

    result = adapter.run_command(["init"])

    assert result.exit_code == 0, result.stdout + result.stderr
    mock_config.set_setting.assert_called_once_with("editor", "nvim")
    mock_config.set_env_variable.assert_not_called()


def test_init_config_command_re_prompts_for_editor(tmp_path, monkeypatch):
    """``teddy init config`` re-runs the gates, re-prompting for the reset editor."""
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_tty(True)
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    mock_config = _configure(env, api_key="sk-present", editor="")
    _discover_nvim(env)
    monkeypatch.setattr("typer.prompt", lambda *a, **k: "1")

    result = adapter.run_command(["init", "config"])

    assert result.exit_code == 0, result.stdout + result.stderr
    mock_config.set_setting.assert_called_once_with("editor", "nvim")
