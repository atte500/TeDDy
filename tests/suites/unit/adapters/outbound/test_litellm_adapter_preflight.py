import pytest
from unittest.mock import Mock
from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter


@pytest.fixture
def adapter(mock_config):
    return LiteLLMAdapter(mock_config)


def test_validate_config_rejects_empty_api_key(adapter, mock_config):
    # Arrange: Config has an empty API key
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "llm.api_key": "",
        "llm.model": "gpt-4",
    }.get(key, default)

    # Act
    errors = adapter.validate_config()

    # Assert
    assert any("empty" in error.lower() for error in errors)
    assert any("llm.api_key" in error for error in errors)


def test_validate_config_detects_missing_env_vars(adapter, mock_config, monkeypatch):
    # Arrange
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "llm.model": "openai/gpt-4"
    }.get(key, default)

    # Mock litellm.validate_environment to return missing keys
    import litellm

    mock_validate = Mock(return_value={"missing_keys": ["OPENAI_API_KEY"]})
    monkeypatch.setattr(litellm, "validate_environment", mock_validate)

    # Act
    errors = adapter.validate_config()

    # Assert
    assert any("Missing required environment variable" in error for error in errors)
    assert any("OPENAI_API_KEY" in error for error in errors)


def test_validate_config_accepts_api_key_from_config(adapter, mock_config, monkeypatch):
    # Arrange: Valid API key in config, but missing from environment
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "llm.api_key": "sk-real-key",  # pragma: allowlist secret
        "llm.model": "openai/gpt-4",
    }.get(key, default)

    # Mock litellm.validate_environment to return missing keys
    import litellm

    mock_validate = Mock(return_value={"missing_keys": ["OPENAI_API_KEY"]})
    monkeypatch.setattr(litellm, "validate_environment", mock_validate)

    # Act
    errors = adapter.validate_config()

    # Assert: OPENAI_API_KEY error should be suppressed because llm.api_key is provided
    assert not any("OPENAI_API_KEY" in error for error in errors)


def test_validate_config_remote_check_timeout(adapter, mock_config, monkeypatch):
    # Arrange: Mock the executor and future to simulate timeout immediately
    from concurrent.futures import TimeoutError

    mock_future = Mock()
    mock_future.result.side_effect = TimeoutError()

    mock_executor = Mock()
    mock_executor.submit.return_value = mock_future

    monkeypatch.setattr(adapter, "_get_executor", lambda: mock_executor)

    mock_config.get_setting.side_effect = lambda key, default=None: {
        "llm.api_key": "sk-real-key",  # pragma: allowlist secret
        "llm.model": "openai/gpt-4",
    }.get(key, default)

    import litellm

    monkeypatch.setattr(
        litellm, "validate_environment", Mock(return_value={"missing_keys": []})
    )

    # Act
    errors = adapter.validate_config(include_remote=True)

    # Assert: Verify that result() was called with EXACTLY 10 seconds
    mock_future.result.assert_called_with(timeout=10.0)
    assert any("timed out after 10 seconds" in error.lower() for error in errors)
