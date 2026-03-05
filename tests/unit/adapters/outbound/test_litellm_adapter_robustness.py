import pytest
from unittest.mock import MagicMock, patch
from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter
from teddy_executor.core.ports.outbound.llm_client import LlmApiError


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.get_setting.return_value = {}
    return config


@pytest.fixture
def adapter(mock_config):
    return LiteLLMAdapter(mock_config)


def test_get_completion_success(adapter):
    # Mock a standard LiteLLM response object
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Verified Content"
    mock_response.choices = [mock_choice]

    with patch("litellm.completion", return_value=mock_response):
        result = adapter.get_completion(
            "test-model", [{"role": "user", "content": "hi"}]
        )
        assert result == "Verified Content"


def test_get_completion_empty_choices(adapter):
    mock_response = MagicMock()
    mock_response.choices = []

    with patch("litellm.completion", return_value=mock_response):
        result = adapter.get_completion(
            "test-model", [{"role": "user", "content": "hi"}]
        )
        assert result == ""


def test_get_completion_none_content(adapter):
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = None
    mock_response.choices = [mock_choice]

    with patch("litellm.completion", return_value=mock_response):
        result = adapter.get_completion(
            "test-model", [{"role": "user", "content": "hi"}]
        )
        assert result == ""


def test_get_completion_error_handling(adapter):
    with patch("litellm.completion", side_effect=Exception("Connection Timeout")):
        with pytest.raises(LlmApiError) as excinfo:
            adapter.get_completion("test-model", [{"role": "user", "content": "hi"}])
        assert "LLM Completion failed" in str(excinfo.value)
