"""Acceptance test for the interactive LLM API-key preflight wiring (Slice 00-27).

Drives the CLI in-process (Subcutaneous Testing) to prove the Tracer Bullet: a
yolo run that already specifies its opening message (``-y -m``) still prompts
for the LLM API key on a TTY when the key is missing, and the entered key is
persisted to the env file.

The API-key gate is deliberately WIDER than the editor gate: the editor is
optional (so ``-y -m`` skips its setup), whereas the key is REQUIRED (so
``-y -m`` on a TTY must still prompt).
"""

from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager

from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.setup.test_environment import TestEnvironment


def test_start_yolo_with_message_prompts_for_api_key_on_tty(tmp_path, monkeypatch):
    """Scenario: a ``-y -m`` run on a TTY still prompts for a missing API key.

    The editor setup is skipped for ``-y -m`` (the editor is optional), but the
    API key is required, so its wider gate (``isatty() and not pipeline``) still
    fires the interactive prompt and persists the entered key.
    """
    # Arrange: TTY-on, missing key, deterministic prompt input.
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_tty(True)
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    mock_config = env.get_service(IConfigService)
    mock_config.get_setting.side_effect = lambda key, default=None: (
        "" if key == "llm.api_key" else default
    )

    mock_prompt_manager = env.mock_port(IPromptManager)
    mock_prompt_manager.get_prompt_content.return_value = "pathfinder prompt"

    monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: "entered-value")

    # Act: yolo with an explicit message -> fully specified, yet the required
    # API key must still trigger the interactive prompt.
    adapter.run_start(["-y", "-m", "hi", "--no-copy"])

    # Assert: the prompt fired and persisted the entered key to the env file.
    mock_config.set_env_variable.assert_called_once_with(
        "TEDDY_LLM_API_KEY", "entered-value"
    )
