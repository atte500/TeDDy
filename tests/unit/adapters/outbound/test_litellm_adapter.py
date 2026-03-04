import pytest
from unittest.mock import MagicMock, patch
from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter
from teddy_executor.core.ports.outbound.llm_client import LlmApiError


def test_get_completion_calls_litellm_correctly():
    # Arrange
    # Mock the response structure of litellm
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "AI response text"

    with patch("litellm.completion", return_value=mock_response) as mock_completion:
        adapter = LiteLLMAdapter()
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
    with patch("litellm.completion", side_effect=RuntimeError("API Failure")):
        adapter = LiteLLMAdapter()

        # Act & Assert
        with pytest.raises(LlmApiError) as excinfo:
            adapter.get_completion(model="any-model", messages=[])

        assert "API Failure" in str(excinfo.value)


def test_get_completion_returns_empty_string_for_empty_choices():
    # Arrange
    mock_response = MagicMock()
    mock_response.choices = []

    with patch("litellm.completion", return_value=mock_response):
        adapter = LiteLLMAdapter()

        # Act
        result = adapter.get_completion(model="gpt-4", messages=[])

        # Assert
        assert result == ""
