import yaml
from teddy_executor.core.ports.outbound.config_service import IConfigService


def test_get_setting_returns_value_from_yaml(fs, container):
    # Arrange
    config_path = ".teddy/config.yaml"
    config_data = {
        "llm_model": "gpt-4",
        "api_key": "secret-key",  # pragma: allowlist secret
    }
    fs.create_dir(".teddy")
    fs.create_file(config_path, contents=yaml.dump(config_data))

    # YamlConfigAdapter is registered as the default IConfigService
    adapter = container.resolve(IConfigService)

    # Act & Assert
    assert adapter.get_setting("llm_model") == "gpt-4"
    assert adapter.get_setting("api_key") == "secret-key"


def test_get_setting_returns_default_for_missing_key(fs, container):
    # Arrange
    config_path = ".teddy/config.yaml"
    fs.create_dir(".teddy")
    fs.create_file(config_path, contents=yaml.dump({"existing": "value"}))

    adapter = container.resolve(IConfigService)

    # Act & Assert
    assert adapter.get_setting("missing", default="fallback") == "fallback"
    assert adapter.get_setting("missing") is None


def test_get_setting_supports_nested_keys(fs, container):
    # Arrange
    expected_timeout = 30
    config_path = ".teddy/config.yaml"
    config_data = {"execution": {"default_timeout_seconds": expected_timeout}}
    fs.create_dir(".teddy")
    fs.create_file(config_path, contents=yaml.dump(config_data))

    adapter = container.resolve(IConfigService)

    # Act & Assert
    assert adapter.get_setting("execution.default_timeout_seconds") == expected_timeout


def test_get_setting_handles_missing_config_file(fs, container):
    # Arrange - Ensure no config file exists
    adapter = container.resolve(IConfigService)

    # Act & Assert
    assert adapter.get_setting("any_key", default="fallback") == "fallback"
    assert adapter.get_setting("any_key") is None


def test_get_setting_handles_invalid_yaml(fs, container):
    # Arrange
    config_path = ".teddy/config.yaml"
    fs.create_dir(".teddy")
    fs.create_file(config_path, contents="{ invalid yaml")

    adapter = container.resolve(IConfigService)

    # Act & Assert
    assert adapter.get_setting("any_key", default="fallback") == "fallback"


def test_get_setting_handles_empty_key(fs, container):
    # Arrange
    config_path = ".teddy/config.yaml"
    fs.create_dir(".teddy")
    fs.create_file(config_path, contents=yaml.dump({"key": "value"}))

    adapter = container.resolve(IConfigService)

    # Act & Assert
    assert adapter.get_setting("", default="fallback") == "fallback"
