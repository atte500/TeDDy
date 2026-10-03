import logging
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


def test_get_completion_cost_falls_back_to_zero_on_hydration_failure(container):
    """
    Ensures that if hydration fails to provide metadata, the adapter
    returns 0.0 instead of crashing.
    """
    # Arrange
    from teddy_executor.adapters.outbound.litellm_adapter import (
        LiteLLMAdapter,
        IOpenRouterHydrator,
    )
    from teddy_executor.core.ports.outbound.config_service import IConfigService

    mock_config = container.resolve(IConfigService)
    mock_hydrator = Mock(spec=IOpenRouterHydrator)
    # Hydrator returns None (metadata not found)
    mock_hydrator.get_metadata.return_value = None

    adapter = LiteLLMAdapter(mock_config, hydrator=mock_hydrator)
    mock_litellm = Mock()
    mock_litellm.completion_cost.side_effect = Exception("This model isn't mapped yet")
    adapter._litellm_initialized = True
    adapter._litellm_module = mock_litellm

    mock_response = Mock()
    mock_response.model = "openrouter/non-existent"

    # Act
    cost = adapter.get_completion_cost(mock_response)

    # Assert
    assert cost == 0.0


def test_supports_pricing_checks_litellm_registry(container):
    """
    Verifies that supports_pricing correctly identifies models with
    and without pricing data in the LiteLLM registry.
    """
    from teddy_executor.core.ports.outbound.llm_client import ILlmClient

    adapter = container.resolve(ILlmClient)

    mock_litellm = Mock()
    mock_litellm.model_cost = {
        "gpt-4": {"input_cost_per_token": 0.00001, "max_input_tokens": 8192},
        "free-model": {"input_cost_per_token": 0.0, "max_input_tokens": 4096},
        "unmapped": {"max_input_tokens": 128000},  # No pricing key
    }
    adapter._litellm_initialized = True
    adapter._litellm_module = mock_litellm

    # Assert
    assert adapter.supports_pricing("gpt-4") is True
    assert adapter.supports_pricing("free-model") is True
    assert adapter.supports_pricing("unmapped") is False
    assert adapter.supports_pricing("completely-unknown") is False


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


def test_get_completion_cost_warns_for_priced_model_failure(container, caplog):
    """A priced model whose cost computation raises must log a WARNING."""
    # Arrange
    from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter
    from teddy_executor.core.ports.outbound.config_service import IConfigService

    mock_config = container.resolve(IConfigService)
    adapter = LiteLLMAdapter(mock_config)

    mock_litellm = Mock()
    mock_litellm.model_cost = {
        "priced-anomaly-model": {"input_cost_per_token": 0.00001}
    }
    mock_litellm.completion_cost.side_effect = Exception("cost blew up")
    adapter._litellm_initialized = True
    adapter._litellm_module = mock_litellm

    mock_response = Mock()
    mock_response.model = "priced-anomaly-model"
    mock_response.usage = Mock(
        prompt_tokens=100,
        completion_tokens=50,
        prompt_tokens_details=None,
        completion_tokens_details=None,
    )

    # Act
    with caplog.at_level(logging.WARNING):
        cost = adapter.get_completion_cost(mock_response)

    # Assert: 0.0 contract preserved AND a WARNING carries identity + usage
    assert cost == 0.0
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any(
        "priced-anomaly-model" in r.getMessage()
        and "100" in r.getMessage()
        and "50" in r.getMessage()
        for r in warnings
    ), caplog.text


def test_get_completion_cost_debug_for_unpriced_model_failure(container, caplog):
    """An unpriced model whose cost computation raises logs DEBUG, not WARNING."""
    # Arrange
    from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter
    from teddy_executor.core.ports.outbound.config_service import IConfigService

    mock_config = container.resolve(IConfigService)
    adapter = LiteLLMAdapter(mock_config)

    mock_litellm = Mock()
    mock_litellm.model_cost = {}
    mock_litellm.completion_cost.side_effect = Exception("cost blew up")
    adapter._litellm_initialized = True
    adapter._litellm_module = mock_litellm

    mock_response = Mock()
    mock_response.model = "unpriced-model"
    mock_response.usage = Mock(
        prompt_tokens=10,
        completion_tokens=5,
        prompt_tokens_details=None,
        completion_tokens_details=None,
    )

    # Act
    with caplog.at_level(logging.DEBUG):
        cost = adapter.get_completion_cost(mock_response)

    # Assert: 0.0 contract preserved, a DEBUG carries identity, and NO WARNING
    assert cost == 0.0
    debugs = [r for r in caplog.records if r.levelno == logging.DEBUG]
    assert any("unpriced-model" in r.getMessage() for r in debugs), caplog.text
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert not any("unpriced-model" in r.getMessage() for r in warnings), caplog.text
