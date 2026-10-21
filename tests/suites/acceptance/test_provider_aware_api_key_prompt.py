"""Acceptance coverage: the key prompt names the provider and the stripped model.

Slice 00-02 (Wiring). An OpenRouter user must see which provider and which model
the pasted credential belongs to, and the input must stay hidden.
"""

from unittest.mock import Mock

import typer

from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager

from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.setup.test_environment import TestEnvironment


def test_openrouter_prompt_names_provider_and_stripped_model(tmp_path, monkeypatch):
    """Scenario: an OpenRouter model prompts with its provider and stripped model."""
    # Arrange: a TTY, a missing key, and an OpenRouter model with full routing.
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_tty(True)
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    mock_config = env.get_service(IConfigService)
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "llm.api_key": "",
        "llm.model": "openrouter/~deepseek/deepseek-flash-latest:nitro",
        "editor": "disabled",
    }.get(key, default)

    mock_llm = env.mock_port(ILlmClient)
    mock_llm.validate_config.return_value = []
    mock_prompt_manager = env.mock_port(IPromptManager)
    mock_prompt_manager.get_prompt_content.return_value = "pathfinder prompt"

    # The harness replaces litellm globally, so arrange both external calls this
    # prompt depends on: the missing-key report and the provider resolve. The
    # measured tuple strips the routing prefix and keeps the OpenRouter slug.
    import litellm

    monkeypatch.setattr(
        litellm,
        "validate_environment",
        Mock(return_value={"missing_keys": ["OPENROUTER_API_KEY"]}),
    )
    monkeypatch.setattr(
        litellm,
        "get_llm_provider",
        Mock(
            return_value=(
                "~deepseek/deepseek-flash-latest:nitro",
                "openrouter",
                None,
                None,
            )
        ),
    )

    prompts: list[tuple[str, dict]] = []

    def _prompt(*args, **kwargs):
        prompts.append((str(args[0]) if args else "", kwargs))
        return "sk-entered"  # pragma: allowlist secret

    monkeypatch.setattr(typer, "prompt", _prompt)

    # Act
    result = adapter.run_start(["-y", "-m", "hi", "--no-copy"])

    # Assert: the prompt fires hidden, names the provider, and strips the prefix.
    combined = result.stdout + result.stderr
    assert prompts, "the OpenRouter configuration must prompt for a key"
    assert prompts[0][0] == "LLM API key"
    assert prompts[0][1].get("hide_input") is True
    assert "Provider: openrouter" in combined, combined
    assert "Model:    ~deepseek/deepseek-flash-latest:nitro" in combined, combined
    assert (
        "Paste your key below, or press Enter on an empty line to skip." in combined
    ), combined
    mock_config.set_env_variable.assert_called_once_with(
        "TEDDY_LLM_API_KEY", "sk-entered"
    )
