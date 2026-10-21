"""Acceptance coverage: ``--api-key`` is gone from the session commands.

An explicit override is now an unknown option, while a resolved ``llm.api_key``
value (the interpolated ``TEDDY_LLM_API_KEY`` state) still starts a session with
no prompt.
"""

import pytest

from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager

from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.setup.test_environment import TestEnvironment


@pytest.mark.parametrize(
    "args",
    [
        ["start", "--api-key", "sk-test"],
        ["resume", "--api-key", "sk-test"],
    ],
)
def test_api_key_flag_is_rejected(tmp_path, monkeypatch, args):
    """An explicit ``--api-key`` override is an unknown option on both commands."""
    TestEnvironment(monkeypatch, tmp_path).setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    result = adapter.run_cli_command(args)

    output = result.stdout + result.stderr
    assert result.exit_code != 0
    assert "No such option" in output


def test_start_uses_resolved_key_without_prompting(tmp_path, monkeypatch):
    """A resolved key value starts a session without any interactive prompt."""
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_tty(True)
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    mock_config = env.get_service(IConfigService)
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "llm.api_key": "sk-from-environment",  # pragma: allowlist secret
        "editor": "disabled",
    }.get(key, default)

    mock_prompt_manager = env.mock_port(IPromptManager)
    mock_prompt_manager.get_prompt_content.return_value = "pathfinder prompt"

    prompts: list[str] = []

    def _prompt(*prompt_args, **prompt_kwargs):
        prompts.append(str(prompt_args[0]) if prompt_args else "")
        return "sk-entered"

    monkeypatch.setattr("typer.prompt", _prompt)

    adapter.run_start(["-y", "-m", "hi", "--no-copy"])

    assert prompts == [], "a resolved API key must not prompt for a key"
    mock_config.set_env_variable.assert_not_called()
