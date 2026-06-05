from typing import Any
from unittest.mock import Mock
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter
from teddy_executor.adapters.outbound.openrouter_hydrator import (
    OpenRouterMetadataHydrator,
)


def test_litellm_adapter_is_wired_with_hydrator(container):
    """
    Ensures that the ILlmClient resolved from the container has
    an OpenRouterMetadataHydrator injected.
    """
    # Act
    llm_client = container.resolve(ILlmClient)

    # Assert
    assert isinstance(llm_client, LiteLLMAdapter)
    # Accessing private attribute for wiring verification
    assert isinstance(llm_client._hydrator, OpenRouterMetadataHydrator)


def test_validation_then_retry_wiring(container, monkeypatch):
    """
    Integration test for the full validation-then-retry flow:
    - Mock config to pass validation.
    - Make litellm fail with a generic error on attempt 1, succeed on attempt 2.
    - Verify retries occur and the successful response is returned.
    """
    # Arrange: Create a mock config service with valid settings
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

    # Register the mock config in the container
    container.register(IConfigService, instance=mock_config)

    # Resolve the adapter (will use our mock config)
    llm_client: LiteLLMAdapter = container.resolve(ILlmClient)

    # Mock litellm.completion to fail once then succeed
    import litellm

    success_response = Mock()
    success_response.choices = [Mock()]
    success_response.choices[0].message.content = "Final response"

    litellm.completion.side_effect = [
        RuntimeError("Connection refused"),  # Attempt 1
        success_response,  # Attempt 2 (success)
    ]

    # Act
    result = llm_client.get_completion(messages=[{"role": "user", "content": "test"}])

    # Assert
    assert litellm.completion.call_count == 2, (
        f"Expected 2 completion calls but got {litellm.completion.call_count}"
    )
    assert result is success_response, "Expected the successful response after retry"
    assert result.choices[0].message.content == "Final response"
