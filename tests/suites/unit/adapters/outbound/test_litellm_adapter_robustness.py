import pytest
from unittest.mock import MagicMock, patch
from teddy_executor.core.ports.outbound.llm_client import ILlmClient, LlmApiError


def test_get_completion_returns_raw_response(container, mock_config):
    mock_config.get_setting.return_value = {}
    adapter = container.resolve(ILlmClient)
    # Mock a standard LiteLLM response object
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Verified Content"
    mock_response.choices = [mock_choice]

    with patch("litellm.completion", return_value=mock_response):
        result = adapter.get_completion(
            "test-model", [{"role": "user", "content": "hi"}]
        )
        # The adapter must return the raw response object per ILlmClient contract
        assert result == mock_response
        assert result.choices[0].message.content == "Verified Content"


def test_get_completion_passthrough_empty_choices(container, mock_config):
    mock_config.get_setting.return_value = {}
    adapter = container.resolve(ILlmClient)
    mock_response = MagicMock()
    mock_response.choices = []

    with patch("litellm.completion", return_value=mock_response):
        result = adapter.get_completion(
            "test-model", [{"role": "user", "content": "hi"}]
        )
        assert result == mock_response
        assert len(result.choices) == 0


def test_get_completion_passthrough_none_content(container, mock_config):
    mock_config.get_setting.return_value = {}
    adapter = container.resolve(ILlmClient)
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = None
    mock_response.choices = [mock_choice]

    with patch("litellm.completion", return_value=mock_response):
        result = adapter.get_completion(
            "test-model", [{"role": "user", "content": "hi"}]
        )
        assert result == mock_response
        assert result.choices[0].message.content is None


def test_get_completion_error_handling(container, mock_config):
    mock_config.get_setting.return_value = {}
    adapter = container.resolve(ILlmClient)
    with patch("litellm.completion", side_effect=Exception("Connection Timeout")):
        with pytest.raises(LlmApiError) as excinfo:
            adapter.get_completion("test-model", [{"role": "user", "content": "hi"}])
        assert "LLM Completion failed" in str(excinfo.value)
