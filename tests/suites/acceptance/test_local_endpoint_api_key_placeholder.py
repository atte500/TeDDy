"""Acceptance coverage: a loopback endpoint receives the placeholder key silently.

Slice 00-02 (Wiring). A developer who points ``llm.api_base`` at a server on
their own machine must never be asked for a credential. Instead, the placeholder
key is written to ``.teddy/.env`` so an OpenAI-compatible server that checks the
Authorization header still starts.
"""

from unittest.mock import Mock

import typer

from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager

from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.setup.test_environment import TestEnvironment

PLACEHOLDER_KEY = "dummy-key-custom-endpoints"


def test_loopback_api_base_persists_placeholder_without_prompting(
    tmp_path, monkeypatch
):
    """Scenario: a loopback ``api_base`` skips the prompt and stores the placeholder."""
    # Arrange: a TTY, a missing key, and an OpenAI-compatible server on loopback.
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_tty(True)
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    mock_config = env.get_service(IConfigService)
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "llm.api_key": "",
        "llm.model": "openai/qwen3-coder-30b",
        "llm.api_base": "http://localhost:8080/v1",
        "editor": "disabled",
    }.get(key, default)

    mock_llm = env.mock_port(ILlmClient)
    mock_llm.validate_config.return_value = []
    mock_prompt_manager = env.mock_port(IPromptManager)
    mock_prompt_manager.get_prompt_content.return_value = "pathfinder prompt"

    # The prefixed openai model still reports a missing provider key, so only the
    # loopback endpoint can keep the prompt closed.
    import litellm

    monkeypatch.setattr(
        litellm,
        "validate_environment",
        Mock(return_value={"missing_keys": ["OPENAI_API_KEY"]}),
    )

    prompts: list[str] = []

    def _prompt(*args, **kwargs):
        prompts.append(str(args[0]) if args else "")
        return "sk-entered"  # pragma: allowlist secret

    monkeypatch.setattr(typer, "prompt", _prompt)

    # Act
    result = adapter.run_start(["-y", "-m", "hi", "--no-copy"])

    # Assert: no prompt fires, the placeholder lands on disk, and the notice names it.
    # Full session completion is out of scope for this tracer bullet, so the
    # assertion stops at the key-gate outcome and its user-facing notice.
    assert prompts == [], "a loopback endpoint must not prompt for a key"
    mock_config.set_env_variable.assert_called_once_with(
        "TEDDY_LLM_API_KEY", PLACEHOLDER_KEY
    )
    mock_config.set_setting.assert_called_once_with(
        "llm.api_key", "${TEDDY_LLM_API_KEY}"
    )
    combined = result.stdout + result.stderr
    assert "Local endpoint detected" in combined
    assert PLACEHOLDER_KEY in combined
