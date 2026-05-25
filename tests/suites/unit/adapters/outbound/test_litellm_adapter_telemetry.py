from unittest.mock import Mock
from teddy_executor.core.ports.outbound.llm_client import ILlmClient


def test_get_token_count_delegates_to_litellm(container):
    adapter = container.resolve(ILlmClient)
    messages = [{"role": "user", "content": "Hello"}]
    model = "gpt-4"

    mock_litellm = Mock()
    mock_litellm.token_counter.return_value = 10
    adapter._litellm_initialized = True
    adapter._litellm_module = mock_litellm

    count = adapter.get_token_count(messages, model)

    assert count == 10
    mock_litellm.token_counter.assert_called_once_with(model=model, messages=messages)


def test_get_completion_cost_handles_deferred_hydration_and_retries(container):
    """
    Simulates the deferred hydration scenario:
    The completion succeeds, but completion_cost throws because the model isn't mapped.
    The adapter must catch the generic exception, parse the ID, hydrate, and retry.
    """
    # Arrange
    from teddy_executor.adapters.outbound.litellm_adapter import (
        LiteLLMAdapter,
        IOpenRouterHydrator,
    )
    from teddy_executor.core.ports.outbound.config_service import IConfigService

    mock_config = container.resolve(IConfigService)

    mock_hydrator = Mock(spec=IOpenRouterHydrator)
    mock_hydrator.get_metadata.return_value = {
        "context_window": 1000,
        "pricing": {"input_cost_per_token": 0.1},
    }

    adapter = LiteLLMAdapter(mock_config, hydrator=mock_hydrator)

    # Mock litellm
    mock_litellm = Mock()
    # The first call to completion_cost raises the generic exception. The second succeeds.
    mock_litellm.completion_cost.side_effect = [
        Exception("This model isn't mapped yet: openrouter/unmapped-model-2024"),
        1.25,
    ]
    mock_litellm.model_cost = {}

    # Inject the mock litellm module
    adapter._litellm_initialized = True
    adapter._litellm_module = mock_litellm

    # Create a dummy response with the model attribute
    mock_response = Mock()
    mock_response.model = "openrouter/unmapped-model-2024"

    # Act
    cost = adapter.get_completion_cost(mock_response)

    # Assert
    assert cost == 1.25
    mock_hydrator.get_metadata.assert_called_once_with("openrouter/unmapped-model-2024")
    # Verify the registry was updated during hydration
    assert "openrouter/unmapped-model-2024" in mock_litellm.model_cost
    assert (
        mock_litellm.model_cost["openrouter/unmapped-model-2024"][
            "input_cost_per_token"
        ]
        == 0.1
    )


def test_get_completion_cost_delegates_to_litellm(container):
    adapter = container.resolve(ILlmClient)
    mock_response = Mock()

    mock_litellm = Mock()
    mock_litellm.completion_cost.return_value = 0.05
    adapter._litellm_initialized = True
    adapter._litellm_module = mock_litellm

    cost = adapter.get_completion_cost(mock_response)

    assert cost == 0.05
    mock_litellm.completion_cost.assert_called_once_with(
        completion_response=mock_response
    )
