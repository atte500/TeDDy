from typing import Any

import pytest
from unittest.mock import Mock
from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter
from teddy_executor.core.domain.models.exceptions import ConfigurationError


@pytest.fixture
def adapter(mock_config):
    return LiteLLMAdapter(mock_config)


def test_validate_config_rejects_empty_api_key(adapter, mock_config, monkeypatch):
    # Arrange: Empty API key on a CLOUD model whose provider key is required.
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "llm.api_key": "",
        "llm.model": "openai/gpt-4",
    }.get(key, default)

    import litellm

    monkeypatch.setattr(
        litellm,
        "validate_environment",
        Mock(return_value={"missing_keys": ["OPENAI_API_KEY"]}),
    )

    # Act
    errors = adapter.validate_config()

    # Assert
    assert any("empty" in error.lower() for error in errors)
    assert any("llm.api_key" in error for error in errors)


def test_validate_config_empty_api_key_message_hints_at_dotenv(
    adapter, mock_config, monkeypatch
):
    """The empty-key error message points the user at .teddy/.env / TEDDY_LLM_API_KEY.

    A cloud model that genuinely requires a key reports a friendly error naming
    the env file and the env var the user must set.
    """
    # Arrange: Empty API key on a CLOUD model whose provider key is required.
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "llm.api_key": "",
        "llm.model": "openai/gpt-4",
    }.get(key, default)

    import litellm

    monkeypatch.setattr(
        litellm,
        "validate_environment",
        Mock(return_value={"missing_keys": ["OPENAI_API_KEY"]}),
    )

    # Act
    errors = adapter.validate_config()

    # Assert - the message names the env file and the env var the user must set
    assert any("TEDDY_LLM_API_KEY" in error for error in errors)
    assert any(".teddy/.env" in error for error in errors)


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

    # Assert - the missing provider key is surfaced with a friendly message
    assert any("OPENAI_API_KEY" in error for error in errors)
    assert any("TEDDY_LLM_API_KEY" in error for error in errors)


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


def test_validate_config_allows_keyless_local_model(adapter, mock_config, monkeypatch):
    """A keyless local model validates cleanly (no API key required)."""
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "llm.api_key": "",
        "llm.model": "lm_studio/local",
    }.get(key, default)

    import litellm

    monkeypatch.setattr(
        litellm,
        "validate_environment",
        Mock(return_value={"keys_in_environment": True, "missing_keys": []}),
    )

    errors = adapter.validate_config()

    assert errors == []


def test_validate_config_ignores_non_key_requirements(
    adapter, mock_config, monkeypatch
):
    """Non-*_API_KEY requirements (e.g. OLLAMA_API_BASE) are advisory."""
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "llm.api_key": "",
        "llm.model": "ollama/llama3",
    }.get(key, default)

    import litellm

    monkeypatch.setattr(
        litellm,
        "validate_environment",
        Mock(return_value={"missing_keys": ["OLLAMA_API_BASE"]}),
    )

    errors = adapter.validate_config()

    assert errors == []


class TestLazyValidationGuard:
    """Tests for the _validated flag in get_completion, preventing redundant validation."""

    def test_lazy_validation_raises_configuration_error_on_invalid_config(
        self, mock_config: Any
    ) -> None:
        """get_completion raises ConfigurationError when validate_config fails, without calling litellm."""
        # Arrange: Config missing API key
        from unittest.mock import Mock

        mock_config.get_setting.side_effect = lambda key, default=None: {
            "llm.model": "gpt-4o",
            "llm.api_key": "",
        }.get(key, default)

        mock_litellm = Mock()
        mock_litellm.validate_environment.return_value = {
            "missing_keys": ["OPENAI_API_KEY"]
        }
        adapter = LiteLLMAdapter(
            config_service=mock_config,
            _litellm_provider=mock_litellm,
        )

        # Act & Assert
        with pytest.raises(ConfigurationError, match="empty"):
            adapter.get_completion(
                messages=[{"role": "user", "content": "hi"}], model="gpt-4o"
            )

        # Assert that no litellm.completion call was made (validation guard fired first)
        mock_litellm.completion.assert_not_called()
