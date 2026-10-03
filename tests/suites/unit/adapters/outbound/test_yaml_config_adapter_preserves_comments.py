"""Regression tests: ``set_setting`` must surgically edit ``config.yaml``.

The defect: ``YamlConfigAdapter.set_setting`` persisted a single setting by
round-tripping the ENTIRE user config through ``yaml.safe_load`` /
``yaml.dump``. That combination carries no comment/layout metadata, so every
write stripped all comments, collapsed blank lines and reordered keys.

These tests assert the observable behaviour the user expects: only the target
line changes; every other byte of the file (comments, ordering, blank lines)
survives. They also guard the empty / ``{}`` document shapes that a naive
surgical rewrite could corrupt.
"""

import yaml

from teddy_executor.adapters.outbound.yaml_config_adapter import YamlConfigAdapter
from teddy_executor.core.ports.outbound.config_service import IConfigService


COMMENT_RICH_CONFIG = """\
# TeDDy Configuration

# The preferred external editor for reviewing and modifying plans/messages.
editor: ""

# Execution Settings
execution:
  default_timeout_seconds: 60
  similarity_threshold: 0.95 # 1.00 means exact match required.
  max_output_lines: 100 # Caps EXECUTE output to the last X lines.
"""


def _read_config(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def test_set_setting_preserves_comments(fs, container):
    """Setting one key must not strip the file's comments."""
    # Arrange
    fs.create_dir(".teddy")
    fs.create_file(".teddy/config.yaml", contents=COMMENT_RICH_CONFIG)
    adapter = container.resolve(IConfigService)

    # Act
    adapter.set_setting("editor", "nvim")

    # Assert - every comment survives the single-key write
    content = _read_config(".teddy/config.yaml")
    assert "# TeDDy Configuration" in content
    assert "# The preferred external editor" in content
    assert "# Caps EXECUTE output" in content


def test_set_setting_preserves_key_order(fs, container):
    """Setting one key must not reorder the file's keys."""
    # Arrange
    fs.create_dir(".teddy")
    fs.create_file(".teddy/config.yaml", contents=COMMENT_RICH_CONFIG)
    adapter = container.resolve(IConfigService)

    # Act
    adapter.set_setting("editor", "nvim")

    # Assert - similarity_threshold stays above max_output_lines (file order)
    content = _read_config(".teddy/config.yaml")
    assert content.index("similarity_threshold") < content.index("max_output_lines")


def test_set_setting_changes_only_the_target_value(fs, container):
    """The edited file must differ from the original only on the editor line."""
    # Arrange
    fs.create_dir(".teddy")
    fs.create_file(".teddy/config.yaml", contents=COMMENT_RICH_CONFIG)
    adapter = container.resolve(IConfigService)

    # Act
    adapter.set_setting("editor", "nvim")

    # Assert - byte-exact: the whole document is identical except the value
    content = _read_config(".teddy/config.yaml")
    expected = COMMENT_RICH_CONFIG.replace('editor: ""', "editor: nvim")
    assert content == expected


def test_set_setting_handles_empty_mapping_document(fs, container):
    """A '{}'-only config file must remain valid YAML after a set."""
    # Arrange
    fs.create_dir(".teddy")
    fs.create_file(".teddy/config.yaml", contents="{}\n")
    adapter = container.resolve(IConfigService)

    # Act
    adapter.set_setting("editor", "nvim")

    # Assert - valid YAML that resolves the written key
    parsed = yaml.safe_load(_read_config(".teddy/config.yaml"))
    assert parsed == {"editor": "nvim"}
    fresh = YamlConfigAdapter(config_path=".teddy/config.yaml")
    assert fresh.get_setting("editor") == "nvim"


def test_set_setting_handles_empty_document(fs, container):
    """An empty config file must be writable without error."""
    # Arrange
    fs.create_dir(".teddy")
    fs.create_file(".teddy/config.yaml", contents="")
    adapter = container.resolve(IConfigService)

    # Act
    adapter.set_setting("editor", "nvim")

    # Assert
    fresh = YamlConfigAdapter(config_path=".teddy/config.yaml")
    assert fresh.get_setting("editor") == "nvim"
