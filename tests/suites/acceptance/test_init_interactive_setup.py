"""Acceptance coverage: ``teddy init`` defers interactive setup to session start.

Bare ``teddy init`` and ``teddy init config`` scaffold files only. On a terminal
they must persist no environment value and prompt for nothing, because the
API-key and editor setup runs at ``teddy start`` and ``teddy resume``, where the
configured values are used. The ``teddy start`` prompt stays covered by
``test_api_key_setup_wiring.py``.
"""

import pytest
import typer

from teddy_executor.core.ports.outbound.config_service import IConfigService

from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.setup.test_environment import TestEnvironment


def _record_prompts(monkeypatch) -> list[str]:
    """Record any interactive prompt so a silent command can be proven."""
    prompts: list[str] = []

    def _prompt(*args, **kwargs):
        prompts.append(str(args[0]) if args else "")
        return "entered-value"

    monkeypatch.setattr(typer, "prompt", _prompt)
    return prompts


def _configure_missing_key_and_disabled_editor(env) -> None:
    """Leave the key missing and the editor disabled so only the key gate is live.

    The ``disabled`` sentinel keeps the editor gate inert. Without it, the old
    editor prompt would loop on an unresolvable command and the Red run would
    hang instead of failing on the assertions under test.
    """
    mock_config = env.get_service(IConfigService)
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "llm.api_key": "",
        "editor": "disabled",
    }.get(key, default)


@pytest.mark.parametrize("args", [["init"], ["init", "config"]])
def test_init_commands_prompt_for_nothing_on_tty(tmp_path, monkeypatch, args):
    """A TTY ``teddy init`` and ``teddy init config`` persist no environment value."""
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_tty(True)
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    _configure_missing_key_and_disabled_editor(env)
    prompts = _record_prompts(monkeypatch)
    mock_config = env.get_service(IConfigService)

    result = adapter.run_command(args)

    assert result.exit_code == 0, result.stdout + result.stderr
    assert prompts == [], f"'{' '.join(args)}' must not prompt on a TTY"
    mock_config.set_env_variable.assert_not_called()
    mock_config.set_setting.assert_not_called()
