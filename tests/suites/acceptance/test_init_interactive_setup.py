"""Acceptance tracer bullet for the interactive setup gates on ``teddy init`` (Slice 00-37).

Drives the outermost CLI boundary to prove that bare ``teddy init`` runs the
same interactive API-key setup as ``teddy start`` when a terminal is attached,
reusing the existing preflight helpers (no new prompt logic). The editor gate is
kept inert here (the mock config reports the ``disabled`` sentinel) so the bullet
stays focused on the API-key path; the editor path and the non-TTY negative are
owned by the init-time prompt coverage deliverable.
"""

from teddy_executor.core.ports.outbound.config_service import IConfigService

from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.setup.test_environment import TestEnvironment


def test_bare_init_on_tty_prompts_for_missing_api_key(tmp_path, monkeypatch):
    """``teddy init`` on a TTY persists an entered key when the key is missing."""
    # Arrange: TTY-on, missing key, key-requiring (unconfigured) model, editor
    # disabled so only the API-key prompt fires.
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_tty(True)
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    mock_config = env.get_service(IConfigService)
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "llm.api_key": "",
        "editor": "disabled",
    }.get(key, default)

    monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: "entered-value")

    # Act: bare `init` on a TTY.
    result = adapter.run_command(["init"])

    # Assert: the API-key gate fired and persisted the entered key.
    assert result.exit_code == 0, result.stdout + result.stderr
    mock_config.set_env_variable.assert_called_once_with(
        "TEDDY_LLM_API_KEY", "entered-value"
    )
