"""Sandbox replica of the wiring test with the isolation fix applied.

The production test asserts an absolute ``litellm.completion.call_count == 2``
against the process-global Mock that ``tests/harness/setup/composition.py``
installs as ``sys.modules["litellm"]``, so any earlier test in the same xdist
worker inflates the counter and the assertion becomes scheduling-dependent.

This replica mirrors the production arrange phase and adds the reset the
proposed harness fixture performs before every test. Because fixtures declared
in ``tests/conftest.py`` do not apply here, it declares its own container
fixture and imports the harness composition module directly to install the
shared double.

Run it with the seeding plugin to prove the fix under inherited calls:
  PYTHONPATH=$PWD/spikes/debug/litellm-call-count-leak uv run pytest \\
    spikes/debug/litellm-call-count-leak/replica_test_llm_wiring.py \\
    -q -n0 -p probe_seeded_counter
"""

from typing import Any
from unittest.mock import Mock

import pytest

import tests.harness.setup.composition  # installs sys.modules["litellm"]
from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter
from teddy_executor.container import create_container
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.session_loop_guard import ISessionLoopGuard


@pytest.fixture
def container(monkeypatch):
    """Sandbox stand-in for the harness container fixture."""
    import teddy_executor.container as container_module

    sandbox_container = create_container()

    class SandboxLoopGuard(ISessionLoopGuard):
        def should_continue(self, turn_count, cumulative_cost, require_approval):
            return False, "sandbox guardrail"

    sandbox_container.register(ISessionLoopGuard, SandboxLoopGuard)
    monkeypatch.setattr(container_module, "_container", sandbox_container)
    return sandbox_container


def test_validation_then_retry_wiring(container):
    """Same flow as production, with the shared counter reset in arrange."""
    mock_config = Mock(spec=IConfigService)

    def _get_setting(key: str, default: Any = None) -> Any:
        if key == "llm":
            return {
                "api_key": "sk-test-key",  # pragma: allowlist secret
                "model": "openrouter/test-model",
                "max_retries": 3,
            }
        config_map = {
            "llm.api_key": "sk-test-key",  # pragma: allowlist secret
            "llm.model": "openrouter/test-model",
            "llm.max_retries": 3,
        }
        return config_map.get(key, default)

    mock_config.get_setting.side_effect = _get_setting
    container.register(IConfigService, instance=mock_config)
    llm_client: LiteLLMAdapter = container.resolve(ILlmClient)

    import litellm

    # The fix: the shared double's history and scripted behaviour belong to the
    # process, not to this test, so both are cleared before arranging.
    litellm.completion.reset_mock()
    litellm.completion.side_effect = None

    success_response = Mock()
    success_response.choices = [Mock()]
    success_response.choices[0].message.content = "Final response"
    litellm.completion.side_effect = [
        RuntimeError("Connection refused"),
        success_response,
    ]

    result = llm_client.get_completion(messages=[{"role": "user", "content": "test"}])

    assert litellm.completion.call_count == 2, (
        f"Expected 2 completion calls but got {litellm.completion.call_count}"
    )
    assert result is success_response, "Expected the successful response after retry"
    assert result.choices[0].message.content == "Final response"
