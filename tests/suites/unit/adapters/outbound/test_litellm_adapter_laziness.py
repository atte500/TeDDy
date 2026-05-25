import pytest
from unittest.mock import Mock
from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter


@pytest.fixture
def mock_config():
    return Mock()


def test_validate_config_does_not_import_litellm_for_empty_key(
    mock_config, monkeypatch
):
    # Arrange
    adapter = LiteLLMAdapter(mock_config)
    mock_get_litellm = Mock()
    monkeypatch.setattr(adapter, "_get_litellm", mock_get_litellm)

    # Config has the default placeholder
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "llm.api_key": "",
        "llm.model": "gpt-4",
    }.get(key, default)

    # Act
    errors = adapter.validate_config()

    # Assert
    assert any("empty" in e.lower() for e in errors)
    mock_get_litellm.assert_not_called()


def test_validate_config_does_not_import_litellm_for_missing_model(
    mock_config, monkeypatch
):
    # Arrange
    adapter = LiteLLMAdapter(mock_config)
    mock_get_litellm = Mock()
    monkeypatch.setattr(adapter, "_get_litellm", mock_get_litellm)

    # Config is missing the model
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "llm.api_key": "sk-real-key",  # pragma: allowlist secret
        "llm.model": None,
    }.get(key, default)

    # Act
    errors = adapter.validate_config()

    # Assert
    assert any("model" in e.lower() and "not configured" in e.lower() for e in errors)
    mock_get_litellm.assert_not_called()
