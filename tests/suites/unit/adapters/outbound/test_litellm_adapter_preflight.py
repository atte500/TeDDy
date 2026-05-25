import pytest
from unittest.mock import Mock
from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter


@pytest.fixture
def adapter(mock_config):
    return LiteLLMAdapter(mock_config)


def test_validate_config_rejects_default_placeholder(adapter, mock_config):
    # Arrange: Config has the default placeholder
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "llm.api_key": "your-api-key",  # pragma: allowlist secret
        "llm.model": "gpt-4",
    }.get(key, default)

    # Act
    errors = adapter.validate_config()

    # Assert
    assert any("default placeholder" in error.lower() for error in errors)
    assert any("llm.api_key" in error for error in errors)


def test_validate_config_rejects_placeholder_case_insensitive(adapter, mock_config):
    # Arrange: Config has the default placeholder with different casing
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "llm.api_key": "YOUR-API-KEY",  # pragma: allowlist secret
        "llm.model": "gpt-4",
    }.get(key, default)

    # Act
    errors = adapter.validate_config()

    # Assert
    assert any("default placeholder" in error.lower() for error in errors)


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
    # Arrange: Mock check_valid_key to hang
    import time

    def slow_check(*args, **kwargs):
        time.sleep(
            4
        )  # Sleep 4s (enough to exceed 2.5s but stay under 5s global timeout)
        return True

    mock_config.get_setting.side_effect = lambda key, default=None: {
        "llm.api_key": "sk-real-key",  # pragma: allowlist secret
        "llm.model": "openai/gpt-4",
    }.get(key, default)

    import litellm

    monkeypatch.setattr(
        litellm, "validate_environment", Mock(return_value={"missing_keys": []})
    )
    monkeypatch.setattr(litellm, "check_valid_key", slow_check)

    # Act: Run with a timer to ensure it returns fast
    start_time = time.time()
    errors = adapter.validate_config(include_remote=True)
    duration = time.time() - start_time

    # Assert
    assert duration < 2.5  # Allow a small buffer for thread overhead
    assert any("timed out" in error.lower() for error in errors)
