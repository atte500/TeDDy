import yaml
from teddy_executor.adapters.outbound.yaml_config_adapter import YamlConfigAdapter
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
    config_data = {"custom": {"default_timeout_seconds": expected_timeout}}
    fs.create_dir(".teddy")
    fs.create_file(config_path, contents=yaml.dump(config_data))

    adapter = container.resolve(IConfigService)

    # Act & Assert
    assert adapter.get_setting("custom.default_timeout_seconds") == expected_timeout


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
    # The typed view owns every declared key, so the caller default applies
    # only to keys the schema does not declare.
    assert adapter.get_setting("undeclared_setting", default="auto") == "auto"


def test_get_setting_output_capping_keys(fs, container):
    # Arrange
    config_data = {
        "execute": {"max_output_lines": 50},
        "read": {"max_lines": 500},
    }
    fs.create_dir(".teddy")
    fs.create_file(".teddy/config.yaml", contents=yaml.dump(config_data))

    adapter = container.resolve(IConfigService)

    # Act & Assert
    assert adapter.get_setting("execute.max_output_lines", 100) == 50
    assert adapter.get_setting("read.max_lines", 1000) == 500
    assert adapter.get_setting("execute.missing_key", 100) == 100


def test_legacy_execution_key_resolves_the_bundled_default(fs, container):
    """A v0.1 execution.* key no longer migrates, so the canonical key keeps its bundled default."""
    # Arrange
    config_data = {"execution": {"max_output_lines": 999}}
    fs.create_dir(".teddy")
    fs.create_file(".teddy/config.yaml", contents=yaml.dump(config_data))

    adapter = container.resolve(IConfigService)

    # Act & Assert
    assert adapter.get_setting("execute.max_output_lines") == 100


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


def test_set_setting_rebuilds_the_typed_view(fs, container):
    """A set_setting write is reflected on the adapter's typed app_config."""
    # Arrange
    fs.create_dir(".teddy")
    fs.create_file(".teddy/config.yaml", contents=yaml.dump({"editor": "code"}))
    adapter = container.resolve(IConfigService)
    assert adapter.app_config.execute.max_output_lines == 100

    # Act
    adapter.set_setting("execute.max_output_lines", 250)

    # Assert
    assert adapter.app_config.execute.max_output_lines == 250


def test_get_setting_returns_the_typed_value_for_a_declared_key(tmp_path):
    """A declared key resolves through the typed view, so a string coerces."""
    # Arrange
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir()
    (teddy_dir / "config.yaml").write_text(
        "execute:\n  max_output_lines: '200'\n", encoding="utf-8"
    )
    adapter = YamlConfigAdapter(
        config_path=".teddy/config.yaml", root_dir=str(tmp_path)
    )
    typed = adapter.app_config.execute.max_output_lines
    assert typed == 200

    # Act
    resolved = adapter.get_setting("execute.max_output_lines")

    # Assert
    assert resolved == typed


def test_get_setting_keeps_llm_api_key_live_on_the_same_adapter(tmp_path, monkeypatch):
    """`llm.api_key` stays on the live walk, so a mid-run `.env` write shows up."""
    # Arrange
    monkeypatch.delenv("TEDDY_LLM_API_KEY", raising=False)
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir()
    (teddy_dir / "config.yaml").write_text(
        'llm:\n  api_key: "${TEDDY_LLM_API_KEY}"\n', encoding="utf-8"
    )
    adapter = YamlConfigAdapter(
        config_path=".teddy/config.yaml", root_dir=str(tmp_path)
    )

    # Act
    adapter.set_env_variable("TEDDY_LLM_API_KEY", "sk-live-midrun")

    # Assert
    assert adapter.get_setting("llm.api_key") == "sk-live-midrun"
