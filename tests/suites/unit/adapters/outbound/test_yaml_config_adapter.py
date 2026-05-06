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


def test_get_setting_retrieves_ui_mode(fs, container):
    # Arrange
    config_path = ".teddy/config.yaml"
    config_data = {"ui_mode": "console"}
    fs.create_dir(".teddy")
    fs.create_file(config_path, contents=yaml.dump(config_data))

    adapter = container.resolve(IConfigService)

    # Act & Assert
    assert adapter.get_setting("ui_mode") == "console"


def test_get_setting_ui_mode_defaults_to_tui_at_call_site(fs, container):
    # Arrange - Empty config
    fs.create_dir(".teddy")
    fs.create_file(".teddy/config.yaml", contents="{}")

    adapter = container.resolve(IConfigService)

    # Act & Assert
    # The adapter itself doesn't have hardcoded defaults,
    # but we verify it respects the default passed by the caller.
    assert adapter.get_setting("ui_mode", default="tui") == "tui"


def test_get_setting_output_capping_keys(fs, container):
    # Arrange
    config_data = {
        "execution": {"max_output_lines": 50},
        "read": {"max_lines": 500},
    }
    fs.create_dir(".teddy")
    fs.create_file(".teddy/config.yaml", contents=yaml.dump(config_data))

    adapter = container.resolve(IConfigService)

    # Act & Assert
    assert adapter.get_setting("execution.max_output_lines", 100) == 50
    assert adapter.get_setting("read.max_lines", 1000) == 500
    assert adapter.get_setting("execution.missing_key", 100) == 100


def test_get_config_path_returns_provided_path(container):
    adapter = container.resolve(IConfigService)
    # The default path in YamlConfigAdapter registration (container.py) is .teddy/config.yaml
    assert adapter.get_config_path() == ".teddy/config.yaml"


def test_auto_pruning_defaults_are_present(fs, container):
    """
    Tests that the auto_pruning configuration defaults are present in the baseline.
    This verifies the 'Contract' deliverable for the configuration layer.
    """
    # Arrange - Map the real baseline file into the fake filesystem
    from importlib import resources

    res_path = resources.files("teddy_executor.resources.config").joinpath(
        "config.yaml"
    )
    fs.add_real_file(str(res_path))

    # Ensure no user config exists to force baseline-only check
    fs.create_dir(".teddy")
    fs.create_file(".teddy/config.yaml", contents="{}")

    adapter = container.resolve(IConfigService)

    # Act & Assert
    assert adapter.get_setting("auto_pruning.enabled") is True
    assert adapter.get_setting("auto_pruning.global_context_threshold") == 100000
    assert adapter.get_setting("auto_pruning.prune_preceding_on_non_green") is True
    assert adapter.get_setting("auto_pruning.prune_validation_failures") is True
