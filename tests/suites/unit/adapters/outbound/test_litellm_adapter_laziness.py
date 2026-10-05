import pytest
from unittest.mock import Mock
from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter


@pytest.fixture
def mock_config():
    return Mock()


def test_validate_config_allows_keyless_local_model(mock_config, monkeypatch):
    """A keyless local model validates cleanly without an API key.

    Key-requiredness is delegated to litellm, so a local backend that needs no
    key (e.g. ``lm_studio``) produces no configuration errors.
    """
    # Arrange
    adapter = LiteLLMAdapter(mock_config)
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

    # Act
    errors = adapter.validate_config()

    # Assert
    assert errors == []


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
