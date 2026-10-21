"""Regression tests for the duplicate-key policy and exact-key precedence.

The approved policy is fail-fast: a repeated mapping key in the user config
stops the load with a ``ConfigurationError``, and ``set_setting`` rewrites the
same location that ``get_setting`` resolves.
"""

import pytest
from teddy_executor.adapters.outbound.yaml_config_adapter import YamlConfigAdapter
from teddy_executor.core.domain.models.exceptions import ConfigurationError
from teddy_executor.core.ports.outbound.config_service import IConfigService


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
