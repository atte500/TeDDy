import pytest
from unittest.mock import MagicMock, patch
from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter
from teddy_executor.core.ports.outbound.llm_client import LlmApiError


def test_get_completion_calls_litellm_correctly():
    # Arrange
    # Mock the response structure of litellm
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "AI response text"
    mock_response.choices = [mock_choice]

    mock_config = MagicMock()
    mock_config.get_setting.return_value = {}

    with patch("litellm.completion", return_value=mock_response) as mock_completion:
        adapter = LiteLLMAdapter(mock_config)
        messages = [{"role": "user", "content": "Hello"}]
        model = "gpt-4"

        # Act
        result = adapter.get_completion(model=model, messages=messages, temperature=0.7)

        # Assert
        assert result == "AI response text"
        mock_completion.assert_called_once_with(
            model=model, messages=messages, temperature=0.7
        )


def test_get_completion_wraps_errors_in_llm_api_error():
    # Arrange
    mock_config = MagicMock()
    mock_config.get_setting.return_value = {}

    with patch("litellm.completion", side_effect=RuntimeError("API Failure")):
        adapter = LiteLLMAdapter(mock_config)

        # Act & Assert
        with pytest.raises(LlmApiError) as excinfo:
            adapter.get_completion(model="any-model", messages=[])

        assert "API Failure" in str(excinfo.value)


def test_get_completion_returns_empty_string_for_empty_choices():
    # Arrange
    mock_response = MagicMock()
    mock_response.choices = []

    mock_config = MagicMock()
    mock_config.get_setting.return_value = {}

    with patch("litellm.completion", return_value=mock_response):
        adapter = LiteLLMAdapter(mock_config)

        # Act
        result = adapter.get_completion(model="gpt-4", messages=[])

        # Assert
        assert result == ""
