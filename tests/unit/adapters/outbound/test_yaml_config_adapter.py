import yaml
from teddy_executor.adapters.outbound.yaml_config_adapter import YamlConfigAdapter


def test_get_setting_returns_value_from_yaml(fs):
    # Arrange
    config_path = ".teddy/config.yaml"
    config_data = {
        "llm_model": "gpt-4",
        "api_key": "secret-key",  # pragma: allowlist secret
    }
    fs.create_dir(".teddy")
    fs.create_file(config_path, contents=yaml.dump(config_data))

    adapter = YamlConfigAdapter(config_path=config_path)

    # Act & Assert
    assert adapter.get_setting("llm_model") == "gpt-4"
    assert adapter.get_setting("api_key") == "secret-key"


def test_get_setting_returns_default_for_missing_key(fs):
    # Arrange
    config_path = ".teddy/config.yaml"
    fs.create_dir(".teddy")
    fs.create_file(config_path, contents=yaml.dump({"existing": "value"}))

    adapter = YamlConfigAdapter(config_path=config_path)

    # Act & Assert
    assert adapter.get_setting("missing", default="fallback") == "fallback"
    assert adapter.get_setting("missing") is None


def test_get_setting_handles_missing_config_file(fs):
    # Arrange
    # No file created
    adapter = YamlConfigAdapter(config_path=".teddy/non_existent.yaml")

    # Act & Assert
    assert adapter.get_setting("any_key", default="fallback") == "fallback"
    assert adapter.get_setting("any_key") is None


def test_get_setting_handles_invalid_yaml(fs):
    # Arrange
    config_path = ".teddy/invalid.yaml"
    fs.create_dir(".teddy")
    fs.create_file(config_path, contents="{ invalid yaml")

    adapter = YamlConfigAdapter(config_path=config_path)

    # Act & Assert
    assert adapter.get_setting("any_key", default="fallback") == "fallback"


def test_get_setting_handles_empty_key(fs):
    # Arrange
    config_path = ".teddy/config.yaml"
    fs.create_dir(".teddy")
    fs.create_file(config_path, contents=yaml.dump({"key": "value"}))

    adapter = YamlConfigAdapter(config_path=config_path)

    # Act & Assert
    assert adapter.get_setting("", default="fallback") == "fallback"
