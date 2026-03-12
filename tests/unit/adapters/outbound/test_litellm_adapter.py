import sys
from unittest.mock import MagicMock
import pytest

# Mock the entire litellm module BEFORE importing the adapter or running tests
# to prevent the expensive 1.2s import and ensure no network calls.
mock_litellm = MagicMock()
sys.modules["litellm"] = mock_litellm

from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter  # noqa: E402
from teddy_executor.core.ports.outbound.llm_client import LlmApiError  # noqa: E402


@pytest.fixture(autouse=True)
def reset_litellm_mock():
    # reset_mock only clears call history, not return_value or side_effect
    mock_litellm.reset_mock()
    mock_litellm.completion.side_effect = None
    mock_litellm.completion.return_value = MagicMock()
    yield


def test_get_completion_calls_litellm_correctly():
    # Arrange
    # Mock the response structure of litellm
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "AI response text"
    mock_response.choices = [mock_choice]
    mock_litellm.completion.return_value = mock_response

    mock_config = MagicMock()
    mock_config.get_setting.return_value = {}

    adapter = LiteLLMAdapter(mock_config)
    messages = [{"role": "user", "content": "Hello"}]
    model = "gpt-4"

    # Act
    result = adapter.get_completion(model=model, messages=messages, temperature=0.7)

    # Assert
    assert result == "AI response text"
    mock_litellm.completion.assert_called_once_with(
        model=model, messages=messages, temperature=0.7
    )


def test_get_completion_wraps_errors_in_llm_api_error():
    # Arrange
    mock_config = MagicMock()
    mock_config.get_setting.return_value = {}
    mock_litellm.completion.side_effect = RuntimeError("API Failure")

    adapter = LiteLLMAdapter(mock_config)

    # Act & Assert
    with pytest.raises(LlmApiError) as excinfo:
        adapter.get_completion(model="any-model", messages=[])

    assert "API Failure" in str(excinfo.value)


def test_get_completion_returns_empty_string_for_empty_choices():
    # Arrange
    mock_response = MagicMock()
    mock_response.choices = []
    mock_litellm.completion.return_value = mock_response

    mock_config = MagicMock()
    mock_config.get_setting.return_value = {}

    adapter = LiteLLMAdapter(mock_config)

    # Act
    result = adapter.get_completion(model="gpt-4", messages=[])

    # Assert
    assert result == ""


def test_config_model_overrides_caller_model():
    # Arrange
    mock_config = MagicMock()
    mock_config.get_setting.return_value = {"model": "config-model-name"}
    adapter = LiteLLMAdapter(mock_config)

    # Act
    adapter.get_completion(model="caller-suggested-model", messages=[])

    # Assert
    mock_litellm.completion.assert_called_once()
    actual_kwargs = mock_litellm.completion.call_args.kwargs
    assert actual_kwargs["model"] == "config-model-name"


def test_config_api_key_overrides_caller_kwargs():
    # Arrange
    mock_config = MagicMock()
    mock_config.get_setting.return_value = {"api_key": "sk-config-key"}
    adapter = LiteLLMAdapter(mock_config)

    # Act
    adapter.get_completion(model="gpt-4", messages=[], api_key="sk-caller-key")

    # Assert
    mock_litellm.completion.assert_called_once()
    actual_kwargs = mock_litellm.completion.call_args.kwargs
    assert actual_kwargs["api_key"] == "sk-config-key"
