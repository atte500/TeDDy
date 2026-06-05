import os
import logging
import pytest
from tests.harness.setup.mocking import POSIXPathMock
from teddy_executor.core.ports.outbound.llm_client import ILlmClient, LlmApiError
from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter


def test_get_completion_returns_raw_response(container, mock_config, monkeypatch):
    config = {"api_key": "sk-test", "model": "test-model", "max_retries": 3}  # pragma: allowlist secret

    def _valid_llm(key: str, default=None):
        return config.get(key.split(".", 1)[1] if "." in key else key, default) if key.startswith("llm") else default

    mock_config.get_setting.side_effect = _valid_llm
    adapter = container.resolve(ILlmClient)
    # Use POSIXPathMock directly for dynamic external library objects
    mock_response = POSIXPathMock()
    mock_choice = POSIXPathMock()
    mock_choice.message.content = "Verified Content"
    mock_response.choices = [mock_choice]

    import litellm

    monkeypatch.setattr(litellm, "completion", lambda **kwargs: mock_response)
    result = adapter.get_completion(
        [{"role": "user", "content": "hi"}], model="test-model"
    )
    # The adapter must return the raw response object per ILlmClient contract
    assert result == mock_response
    assert result.choices[0].message.content == "Verified Content"


def test_get_completion_passthrough_empty_choices(container, mock_config, monkeypatch):
    config = {"api_key": "sk-test", "model": "test-model", "max_retries": 3}  # pragma: allowlist secret

    def _valid_llm(key: str, default=None):
        return config.get(key.split(".", 1)[1] if "." in key else key, default) if key.startswith("llm") else default

    mock_config.get_setting.side_effect = _valid_llm
    adapter = container.resolve(ILlmClient)
    mock_response = POSIXPathMock()
    mock_response.choices = []

    import litellm

    monkeypatch.setattr(litellm, "completion", lambda **kwargs: mock_response)
    result = adapter.get_completion(
        [{"role": "user", "content": "hi"}], model="test-model"
    )
    assert result == mock_response
    assert len(result.choices) == 0


def test_get_completion_passthrough_none_content(container, mock_config, monkeypatch):
    config = {"api_key": "sk-test", "model": "test-model", "max_retries": 3}  # pragma: allowlist secret

    def _valid_llm(key: str, default=None):
        return config.get(key.split(".", 1)[1] if "." in key else key, default) if key.startswith("llm") else default

    mock_config.get_setting.side_effect = _valid_llm
    adapter = container.resolve(ILlmClient)
    mock_response = POSIXPathMock()
    mock_choice = POSIXPathMock()
    mock_choice.message.content = None
    mock_response.choices = [mock_choice]

    import litellm

    monkeypatch.setattr(litellm, "completion", lambda **kwargs: mock_response)
    result = adapter.get_completion(
        [{"role": "user", "content": "hi"}], model="test-model"
    )
    assert result == mock_response
    assert result.choices[0].message.content is None


def test_get_completion_error_handling(container, mock_config, monkeypatch):
    config = {"api_key": "sk-test", "model": "test-model", "max_retries": 3}  # pragma: allowlist secret

    def _valid_llm(key: str, default=None):
        return config.get(key.split(".", 1)[1] if "." in key else key, default) if key.startswith("llm") else default

    mock_config.get_setting.side_effect = _valid_llm
    adapter = container.resolve(ILlmClient)

    import litellm

    def mock_fail(**kwargs):
        raise Exception("Connection Timeout")

    monkeypatch.setattr(litellm, "completion", mock_fail)
    with pytest.raises(LlmApiError) as excinfo:
        adapter.get_completion([{"role": "user", "content": "hi"}], model="test-model")
    assert "LLM Completion failed" in str(excinfo.value)


def test_litellm_initialization_silences_logging_at_critical_level(
    mock_config, monkeypatch
):
    # Arrange
    adapter = LiteLLMAdapter(config_service=mock_config)

    # Act
    # monkeypatch isolates changes to os.environ for the duration of the test
    monkeypatch.setenv("LITELLM_LOG", "NONE")
    # We trigger the lazy import which calls _ensure_silence
    adapter.get_token_count([], model="gpt-4o")

    # Assert
    assert os.environ.get("LITELLM_LOG") == "CRITICAL"
    assert logging.getLogger("LiteLLM").level == logging.CRITICAL
