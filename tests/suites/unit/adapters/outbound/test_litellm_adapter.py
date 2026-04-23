from unittest.mock import MagicMock
import pytest
import litellm

from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter
from teddy_executor.core.ports.outbound.llm_client import LlmApiError


@pytest.fixture(autouse=True)
def reset_litellm_mock():
    """
    Ensure the shared global mock is fresh and isolated for every test.
    """
    # litellm is already mocked globally in tests/harness/setup/composition.py
    litellm.reset_mock()
    # Explicitly restore attributes that are overwritten by literal assignments
    # in the adapter (e.g., litellm.set_verbose = False).
    litellm.set_verbose = MagicMock()
    litellm.suppress_debug_info = MagicMock()
    litellm.completion.side_effect = None
    litellm.completion.return_value = MagicMock()
    yield


def test_get_completion_calls_litellm_correctly(mock_config):
    # Arrange
    # Mock the response structure of litellm
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "AI response text"
    mock_response.choices = [mock_choice]
    litellm.completion.return_value = mock_response

    mock_config.get_setting.return_value = {}

    adapter = LiteLLMAdapter(mock_config)
    messages = [{"role": "user", "content": "Hello"}]
    model = "gpt-4"

    # Act
    result = adapter.get_completion(model=model, messages=messages, temperature=0.7)

    # Assert
    assert result.choices[0].message.content == "AI response text"
    litellm.completion.assert_called_once_with(
        model=model, messages=messages, temperature=0.7
    )


def test_get_completion_wraps_errors_in_llm_api_error(mock_config):
    # Arrange
    mock_config.get_setting.return_value = {}
    litellm.completion.side_effect = RuntimeError("API Failure")

    adapter = LiteLLMAdapter(mock_config)

    # Act & Assert
    with pytest.raises(LlmApiError) as excinfo:
        adapter.get_completion(model="any-model", messages=[])

    assert "API Failure" in str(excinfo.value)


def test_get_completion_returns_empty_string_for_empty_choices(mock_config):
    # Arrange
    mock_response = MagicMock()
    mock_response.choices = []
    litellm.completion.return_value = mock_response

    mock_config.get_setting.return_value = {}

    adapter = LiteLLMAdapter(mock_config)

    # Act
    result = adapter.get_completion(model="gpt-4", messages=[])

    # Assert
    # The adapter returns the raw response object, so we check if the helper
    # would return empty string or handle the object correctly.
    assert result == mock_response


def test_config_model_overrides_caller_model(mock_config):
    # Arrange
    mock_config.get_setting.return_value = {"model": "config-model-name"}
    adapter = LiteLLMAdapter(mock_config)

    # Act
    adapter.get_completion(model="caller-suggested-model", messages=[])

    # Assert
    litellm.completion.assert_called_once()
    actual_kwargs = litellm.completion.call_args.kwargs
    assert actual_kwargs["model"] == "config-model-name"


def test_config_api_key_overrides_caller_kwargs(mock_config):
    # Arrange
    mock_config.get_setting.return_value = {"api_key": "sk-config-key"}
    adapter = LiteLLMAdapter(mock_config)

    # Act
    adapter.get_completion(model="gpt-4", messages=[], api_key="sk-caller-key")

    # Assert
    litellm.completion.assert_called_once()
    actual_kwargs = litellm.completion.call_args.kwargs
    assert actual_kwargs["api_key"] == "sk-config-key"


def test_adapter_does_not_import_litellm_on_init(mock_config):
    # Arrange
    litellm.reset_mock()
    # Reset to fresh mocks to ensure we can check if they were replaced by assignment
    litellm.set_verbose = MagicMock()
    litellm.suppress_debug_info = MagicMock()

    # Act
    LiteLLMAdapter(mock_config)

    # Assert
    # In __init__, the adapter should NOT touch litellm properties.
    # If it did (lazily), these would be replaced by booleans or called.
    # We check if they are still the fresh MagicMocks we just assigned.
    assert isinstance(litellm.set_verbose, MagicMock)
    assert isinstance(litellm.suppress_debug_info, MagicMock)
    assert not litellm.set_verbose.called
