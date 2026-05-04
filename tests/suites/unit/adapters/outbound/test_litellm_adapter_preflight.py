import pytest
from unittest.mock import MagicMock
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


def test_validate_config_detects_missing_env_vars(adapter, mock_config):
    # Arrange
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "llm.model": "openai/gpt-4"
    }.get(key, default)

    # Mock litellm.validate_environment to return missing keys
    with MagicMock() as mock_validate:
        mock_validate.return_value = {"missing_keys": ["OPENAI_API_KEY"]}
        import unittest.mock

        with unittest.mock.patch("litellm.validate_environment", mock_validate):
            # Act
            errors = adapter.validate_config()

    # Assert
    assert any("Missing required environment variable" in error for error in errors)
    assert any("OPENAI_API_KEY" in error for error in errors)


def test_validate_config_accepts_api_key_from_config(adapter, mock_config):
    # Arrange: Valid API key in config, but missing from environment
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "llm.api_key": "sk-real-key",  # pragma: allowlist secret
        "llm.model": "openai/gpt-4",
    }.get(key, default)

    # Mock litellm.validate_environment to return missing keys
    with MagicMock() as mock_validate:
        mock_validate.return_value = {"missing_keys": ["OPENAI_API_KEY"]}
        import unittest.mock

        with unittest.mock.patch("litellm.validate_environment", mock_validate):
            # Act
            errors = adapter.validate_config()

    # Assert: OPENAI_API_KEY error should be suppressed because llm.api_key is provided
    assert not any("OPENAI_API_KEY" in error for error in errors)
