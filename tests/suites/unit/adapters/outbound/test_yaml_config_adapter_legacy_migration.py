"""Unit tests for the legacy execution-key migration.

A user config that predates the execute/edit split still carries the legacy
``execution.*`` keys. The loader copies each tuned value to its canonical
group so production readers resolve it, while the user file stays untouched.
"""

import yaml

from teddy_executor.adapters.outbound.yaml_config_adapter import YamlConfigAdapter


def _load_adapter(tmp_path, user_config):
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir(exist_ok=True)
    (teddy_dir / "config.yaml").write_text(
        yaml.safe_dump(user_config), encoding="utf-8"
    )
    return YamlConfigAdapter(config_path=".teddy/config.yaml", root_dir=str(tmp_path))


def test_legacy_execution_keys_migrate_to_canonical_groups(tmp_path):
    adapter = _load_adapter(
        tmp_path,
        {
            "execution": {
                "default_timeout_seconds": 42.5,
                "max_output_lines": 999,
                "similarity_threshold": 0.8,
            }
        },
    )

    assert adapter.get_setting("execute.default_timeout_seconds") == 42.5
    assert adapter.get_setting("execute.max_output_lines") == 999
    assert adapter.get_setting("edit.similarity_threshold") == 0.8


def test_new_key_wins_when_user_file_carries_both(tmp_path):
    adapter = _load_adapter(
        tmp_path,
        {
            "execution": {"max_output_lines": 111},
            "execute": {"max_output_lines": 222},
        },
    )

    assert adapter.get_setting("execute.max_output_lines") == 222


def test_legacy_none_value_does_not_override_the_baseline(tmp_path):
    adapter = _load_adapter(tmp_path, {"execution": {"max_output_lines": None}})

    assert adapter.get_setting("execute.max_output_lines") == 100


def test_non_dict_target_group_is_replaced(tmp_path):
    adapter = _load_adapter(
        tmp_path,
        {
            "execution": {"max_output_lines": 555},
            "execute": "not-a-mapping",
        },
    )

    assert adapter.get_setting("execute.max_output_lines") == 555


def test_non_dict_legacy_parent_is_left_alone(tmp_path):
    adapter = _load_adapter(tmp_path, {"execution": "not-a-mapping"})

    assert adapter.get_setting("execute.max_output_lines") == 100
