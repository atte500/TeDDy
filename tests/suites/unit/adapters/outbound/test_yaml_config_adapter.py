import pytest
import yaml
from teddy_executor.adapters.outbound.yaml_config_adapter import YamlConfigAdapter
from teddy_executor.core.domain.models.exceptions import ConfigurationError
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


def test_get_setting_retrieves_scalar_value(fs, container):
    # Arrange
    config_path = ".teddy/config.yaml"
    config_data = {"editor": "nvim"}
    fs.create_dir(".teddy")
    fs.create_file(config_path, contents=yaml.dump(config_data))

    adapter = container.resolve(IConfigService)

    # Act & Assert
    assert adapter.get_setting("editor") == "nvim"


def test_get_setting_respects_caller_default_at_call_site(fs, container):
    # Arrange - Empty config
    fs.create_dir(".teddy")
    fs.create_file(".teddy/config.yaml", contents="{}")

    adapter = container.resolve(IConfigService)

    # Act & Assert
    # The adapter itself doesn't have hardcoded defaults,
    # but we verify it respects the default passed by the caller.
    assert adapter.get_setting("editor", default="auto") == "auto"


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
    assert adapter.get_setting("auto_pruning.turn_context_threshold") == 50000
    assert adapter.get_setting("auto_pruning.prune_failure_history") is True
    assert adapter.get_setting("auto_pruning.prune_validation_failures") is True
    assert adapter.get_setting("auto_pruning.preserve_message_turns") is True


def test_editor_default_is_empty_in_baseline(fs, container):
    """
    Tests that the bundled baseline ships an empty editor default and no
    diff_flags override (Slice 03-01 Contract).

    An empty editor default ensures the preflight discovery prompt is the
    single source of editor configuration instead of a hardcoded fallback,
    and the commented-out diff_flags key means no override is active.
    """
    # Arrange - Map the real baseline file into the fake filesystem
    from importlib import resources

    res_path = resources.files("teddy_executor.resources.config").joinpath(
        "config.yaml"
    )
    fs.add_real_file(str(res_path))

    # Ensure no user config overrides the baseline
    fs.create_dir(".teddy")
    fs.create_file(".teddy/config.yaml", contents="{}")

    adapter = container.resolve(IConfigService)

    # Act & Assert
    assert adapter.get_setting("editor") == ""
    assert adapter.get_setting("diff_flags") is None


def test_set_setting_persists_value_and_syncs_cache(fs, container):
    """set_setting persists to the user config AND updates the in-memory cache."""
    # Arrange
    fs.create_dir(".teddy")
    fs.create_file(".teddy/config.yaml", contents=yaml.dump({"editor": "code"}))
    adapter = container.resolve(IConfigService)

    # Act
    adapter.set_setting("editor", "nvim")

    # Assert - same-adapter cache reflects the change without a reload
    assert adapter.get_setting("editor") == "nvim"
    # Assert - persisted to disk (verified via a fresh adapter)
    fresh = YamlConfigAdapter(config_path=".teddy/config.yaml")
    assert fresh.get_setting("editor") == "nvim"


def test_set_setting_creates_config_file_and_parent_directory(fs, container):
    """set_setting creates the config file and its parent directory when missing."""
    # Arrange - no .teddy directory or config file exists yet
    adapter = container.resolve(IConfigService)
    assert not fs.exists(".teddy/config.yaml")

    # Act
    adapter.set_setting("editor", "nvim")

    # Assert - file and parent directory were created
    assert fs.exists(".teddy/config.yaml")
    fresh = YamlConfigAdapter(config_path=".teddy/config.yaml")
    assert fresh.get_setting("editor") == "nvim"


def test_set_setting_supports_dot_notation(fs, container):
    """set_setting resolves nested keys via dot-notation."""
    # Arrange
    fs.create_dir(".teddy")
    fs.create_file(".teddy/config.yaml", contents=yaml.dump({"editor": "code"}))
    adapter = container.resolve(IConfigService)

    # Act
    adapter.set_setting("llm.model", "gpt-4")

    # Assert - same-adapter cache and disk both reflect the nested write
    assert adapter.get_setting("llm.model") == "gpt-4"
    fresh = YamlConfigAdapter(config_path=".teddy/config.yaml")
    assert fresh.get_setting("llm.model") == "gpt-4"


def test_set_setting_preserves_other_keys(fs, container):
    """set_setting preserves unrelated keys in the user config file."""
    # Arrange
    fs.create_dir(".teddy")
    fs.create_file(
        ".teddy/config.yaml",
        contents=yaml.dump({"editor": "code", "other": "keep"}),
    )
    adapter = container.resolve(IConfigService)

    # Act
    adapter.set_setting("editor", "nvim")

    # Assert
    fresh = YamlConfigAdapter(config_path=".teddy/config.yaml")
    assert fresh.get_setting("editor") == "nvim"
    assert fresh.get_setting("other") == "keep"


def test_duplicate_scalar_key_raises_configuration_error(fs, container):
    """A repeated scalar key stops the load with a clear configuration error."""
    # Arrange
    fs.create_dir(".teddy")
    fs.create_file(".teddy/config.yaml", contents="editor: first\neditor: second\n")

    # Act & Assert
    with pytest.raises(ConfigurationError, match=r"editor.*line 2"):
        container.resolve(IConfigService)


def test_duplicate_nested_key_raises_configuration_error(fs, container):
    """A repeated key at any depth stops the load, not just at the root."""
    # Arrange
    fs.create_dir(".teddy")
    fs.create_file(
        ".teddy/config.yaml",
        contents="execution:\n  max_output_lines: 5\n  max_output_lines: 9\n",
    )

    # Act & Assert
    with pytest.raises(ConfigurationError, match="max_output_lines"):
        container.resolve(IConfigService)


def test_duplicate_mapping_key_raises_configuration_error(fs, container):
    """A repeated mapping key stops the load instead of dropping siblings."""
    # Arrange
    fs.create_dir(".teddy")
    fs.create_file(
        ".teddy/config.yaml",
        contents=(
            "execution:\n"
            "  max_output_lines: 5\n"
            "execution:\n"
            "  similarity_threshold: 0.9\n"
        ),
    )

    # Act & Assert
    with pytest.raises(ConfigurationError, match="execution"):
        container.resolve(IConfigService)


def test_set_setting_honours_exact_top_level_dotted_key(fs, container):
    """A flat dotted key wins the write, matching the get_setting precedence."""
    # Arrange
    fs.create_dir(".teddy")
    fs.create_file(
        ".teddy/config.yaml",
        contents='llm:\n  model: nested-value\n"llm.model": flat-value\n',
    )
    adapter = container.resolve(IConfigService)
    assert adapter.get_setting("llm.model") == "flat-value"

    # Act
    adapter.set_setting("llm.model", "new")

    # Assert - the flat key is rewritten in place and the nested key survives
    with open(".teddy/config.yaml", "r", encoding="utf-8") as f:
        content = f.read()
    assert '"llm.model": new' in content
    assert "model: nested-value" in content
    assert adapter.get_setting("llm.model") == "new"
    fresh = YamlConfigAdapter(config_path=".teddy/config.yaml")
    assert fresh.get_setting("llm.model") == "new"


def test_set_setting_rewrites_quoted_nested_key(fs, container):
    """A quoted key token still matches the dotted path during a write."""
    # Arrange
    fs.create_dir(".teddy")
    fs.create_file(".teddy/config.yaml", contents='llm:\n  "model": old\n')
    adapter = container.resolve(IConfigService)

    # Act
    adapter.set_setting("llm.model", "new")

    # Assert
    with open(".teddy/config.yaml", "r", encoding="utf-8") as f:
        content = f.read()
    assert '"model": new' in content
    fresh = YamlConfigAdapter(config_path=".teddy/config.yaml")
    assert fresh.get_setting("llm.model") == "new"


def test_complex_key_falls_back_to_baseline(fs, container):
    """A non-scalar key stays an unreadable user config instead of a crash."""
    # Arrange - map the real baseline file into the fake filesystem
    from importlib import resources

    res_path = resources.files("teddy_executor.resources.config").joinpath(
        "config.yaml"
    )
    fs.add_real_file(str(res_path))
    fs.create_dir(".teddy")
    fs.create_file(".teddy/config.yaml", contents="? [a, b]\n: value\n")

    # Act
    adapter = container.resolve(IConfigService)

    # Assert - the user config is ignored and the baseline still resolves
    assert isinstance(adapter.get_setting("execution.max_output_lines"), int)
