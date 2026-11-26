"""Unit coverage for typed configuration schema construction.

Each declared key resolves with exact-flat-first then nested precedence. A
safe string coerces to the declared type, a missing value falls back to the
schema default, and an uncoercible value raises ``ConfigurationError`` naming
the key. The hyphenated ``workspace.pre-commit`` YAML key maps to the
``pre_commit`` Python field.
"""

import dataclasses
import re
from pathlib import Path

import pytest

import teddy_executor
from teddy_executor.adapters.outbound.yaml_config_adapter import YamlConfigAdapter
from teddy_executor.core.domain.models.config_schema import (
    DEFAULT_APP_CONFIG,
    AutoPruningConfig,
    construct_app_config,
    is_declared_key,
    read_declared_value,
)
from teddy_executor.core.domain.models.exceptions import ConfigurationError


def test_missing_values_use_the_schema_defaults():
    """A merged mapping with no declared key resolves the full default view."""
    assert construct_app_config({}) == DEFAULT_APP_CONFIG


def test_nested_value_overrides_the_default():
    """A nested override replaces only the named field."""
    config = construct_app_config({"execute": {"max_output_lines": 200}})

    assert config.execute.max_output_lines == 200


def test_string_integer_is_coerced():
    """A clean integer string coerces to the declared int field."""
    config = construct_app_config({"execute": {"max_output_lines": "200"}})

    assert config.execute.max_output_lines == 200


def test_string_float_is_coerced():
    """A clean float string coerces to the declared float field."""
    config = construct_app_config({"edit": {"similarity_threshold": "0.8"}})

    assert config.edit.similarity_threshold == pytest.approx(0.8)


@pytest.mark.parametrize("text", ["false", "no", "off", "FALSE", "No"])
def test_string_boolean_false_forms_are_coerced(text):
    """Every documented false spelling coerces to a real boolean."""
    config = construct_app_config({"workspace": {"init": text}})

    assert config.workspace.init is False


def test_hyphenated_key_maps_to_the_python_field():
    """The YAML ``pre-commit`` key fills the ``pre_commit`` Python field."""
    config = construct_app_config({"workspace": {"pre-commit": False}})

    assert config.workspace.pre_commit is False


def test_uncoercible_integer_raises_naming_the_key():
    """An unparseable integer value stops construction, naming the key."""
    with pytest.raises(ConfigurationError, match="execute.max_output_lines"):
        construct_app_config({"execute": {"max_output_lines": "one hundred"}})


def test_uncoercible_float_raises_naming_the_key():
    """An unparseable float value stops construction, naming the key."""
    with pytest.raises(ConfigurationError, match="edit.similarity_threshold"):
        construct_app_config({"edit": {"similarity_threshold": "high"}})


def test_uncoercible_boolean_raises_naming_the_key():
    """An unrecognised boolean spelling stops construction, naming the key."""
    with pytest.raises(ConfigurationError, match="workspace.init"):
        construct_app_config({"workspace": {"init": "maybe"}})


def test_unknown_key_is_ignored():
    """An undeclared key is tolerated and leaves the default view intact."""
    config = construct_app_config({"unknown_group": {"some_key": True}})

    assert config == DEFAULT_APP_CONFIG


def test_exact_flat_dotted_key_wins_over_nested():
    """A flat dotted key outranks the nested path, matching ``get_setting``."""
    config = construct_app_config(
        {
            "execute": {"max_output_lines": 100},
            "execute.max_output_lines": 200,
        }
    )

    assert config.execute.max_output_lines == 200


@pytest.mark.parametrize("value", [-0.01, 1.01])
def test_similarity_threshold_outside_the_range_raises(value):
    """A threshold outside the closed interval zero to one is rejected."""
    with pytest.raises(ConfigurationError, match="edit.similarity_threshold"):
        construct_app_config({"edit": {"similarity_threshold": value}})


@pytest.mark.parametrize("value", [0.0, 1.0])
def test_similarity_threshold_bounds_are_accepted(value):
    """Both interval endpoints are valid thresholds."""
    config = construct_app_config({"edit": {"similarity_threshold": value}})

    assert config.edit.similarity_threshold == pytest.approx(value)


def test_negative_tree_depth_raises():
    """A negative depth is rejected, because a negative cap is meaningless."""
    with pytest.raises(ConfigurationError, match="context.max_depth"):
        construct_app_config({"context": {"max_depth": -1}})


def test_zero_tree_depth_is_accepted():
    """A depth of zero is a valid literal cap that collapses the tree to one notice."""
    config = construct_app_config({"context": {"max_depth": 0}})

    assert config.context.max_depth == 0


def test_default_tree_depth_is_three():
    """The shipped depth cap defaults to three levels."""
    assert DEFAULT_APP_CONFIG.context.max_depth == 3


def test_default_tree_width_is_twenty():
    """The shipped width cap defaults to twenty entries per directory."""
    assert DEFAULT_APP_CONFIG.context.max_children == 20


def test_nested_tree_width_overrides_the_default():
    """A nested override replaces the width cap."""
    config = construct_app_config({"context": {"max_children": 5}})

    assert config.context.max_children == 5


def test_default_plan_context_cap_is_1500_lines():
    """The shipped plan context cap defaults to 1500 lines."""
    assert DEFAULT_APP_CONFIG.plan.max_lines == 1500


def test_nested_plan_max_lines_overrides_the_default():
    """A nested override replaces the plan display cap."""
    config = construct_app_config({"plan": {"max_lines": 200}})

    assert config.plan.max_lines == 200


@pytest.mark.parametrize(
    ("group", "key"),
    [
        ("execute", "max_output_lines"),
        ("read", "max_lines"),
        ("research", "max_results"),
        ("context", "max_children"),
        ("plan", "max_lines"),
    ],
)
def test_zero_capacity_raises(group, key):
    """Every positive-only capacity rejects a zero value."""
    with pytest.raises(ConfigurationError, match=f"{group}.{key}"):
        construct_app_config({group: {key: 0}})


@pytest.mark.parametrize(
    ("group", "key"),
    [
        ("execute", "max_output_lines"),
        ("read", "max_lines"),
        ("research", "max_results"),
        ("context", "max_children"),
        ("plan", "max_lines"),
    ],
)
def test_single_capacity_is_accepted(group, key):
    """A capacity of one is the smallest valid value."""
    config = construct_app_config({group: {key: 1}})

    assert getattr(getattr(config, group), key) == 1


# --- Update source ---


def test_default_update_source_is_empty():
    """The schema default leaves the update source unset, meaning official PyPI."""
    assert DEFAULT_APP_CONFIG.update.index_url == ""


def test_nested_update_source_overrides_the_default():
    """A nested override replaces the update source."""
    config = construct_app_config(
        {"update": {"index_url": "https://example.test/pypi/teddy-cli/json"}}
    )

    assert config.update.index_url == "https://example.test/pypi/teddy-cli/json"


def test_empty_update_source_falls_back_to_the_default():
    """An empty value resolves the schema default, matching every other key."""
    config = construct_app_config({"update": {"index_url": ""}})

    assert config.update.index_url == ""


@pytest.mark.parametrize("value", [42, ["https://example.test/pypi/json"]])
def test_non_string_update_source_raises_naming_the_key(value):
    """A number or list stops construction, naming the update key."""
    with pytest.raises(ConfigurationError, match="update\\.index_url"):
        construct_app_config({"update": {"index_url": value}})


# --- Retention batch cadence ---


def test_default_retention_batch_is_five():
    """The shipped retention batch defaults to five turns."""
    assert DEFAULT_APP_CONFIG.auto_pruning.retention_batch == 5


def test_nested_retention_batch_overrides_the_default():
    """A nested override replaces the retention batch."""
    config = construct_app_config({"auto_pruning": {"retention_batch": 2}})

    assert config.auto_pruning.retention_batch == 2


def test_string_retention_batch_is_coerced():
    """A clean integer string coerces to the declared int field."""
    config = construct_app_config({"auto_pruning": {"retention_batch": "3"}})

    assert config.auto_pruning.retention_batch == 3


def test_single_retention_batch_is_accepted():
    """A batch of one is the escape hatch that keeps the per-turn cadence."""
    config = construct_app_config({"auto_pruning": {"retention_batch": 1}})

    assert config.auto_pruning.retention_batch == 1


@pytest.mark.parametrize("value", [0, -3])
def test_non_positive_retention_batch_raises_naming_the_key(value):
    """A batch below one is rejected, naming the key."""
    with pytest.raises(ConfigurationError, match=r"auto_pruning\.retention_batch"):
        construct_app_config({"auto_pruning": {"retention_batch": value}})


# --- Retired plan-status key ---

_RETIRED_PLAN_STATUS_KEY = "auto_pruning.prune_failure_history"


def test_retired_plan_status_key_is_no_longer_declared():
    """The plan-status heuristic is gone, so the schema stops declaring its key.

    A user who keeps the line in ``config.yaml`` gets it dropped silently, the
    same tolerance every undeclared group already receives.
    """
    assert not is_declared_key(_RETIRED_PLAN_STATUS_KEY)
    assert _RETIRED_PLAN_STATUS_KEY.rsplit(".", 1)[-1] not in {
        field.name for field in dataclasses.fields(AutoPruningConfig)
    }


# --- Documentation / schema drift closure ---

_DOC_PATH = (
    Path(teddy_executor.__file__).resolve().parents[2]
    / "docs"
    / "architecture"
    / "core"
    / "ports"
    / "outbound"
    / "config_service.md"
)


def _documented_configuration_keys() -> list[str]:
    """Return every documented key except the ``llm.*`` passthrough."""
    line = next(
        raw
        for raw in _DOC_PATH.read_text(encoding="utf-8").splitlines()
        if raw.startswith("- **Configuration keys:**")
    )
    return [key for key in re.findall(r"`([^`]+)`", line) if "*" not in key]


def test_documentation_and_schema_declare_the_same_keys():
    """Every documented key exists in the schema, so the two cannot drift."""
    documented = _documented_configuration_keys()
    missing = [key for key in documented if not is_declared_key(key)]

    assert missing == [], f"Documented keys missing from the schema: {missing}"


def test_every_documented_key_resolves_through_get_setting(tmp_path):
    """Every documented key is reachable and matches its typed value."""
    adapter = YamlConfigAdapter(
        config_path=".teddy/config.yaml", root_dir=str(tmp_path)
    )

    for key in _documented_configuration_keys():
        assert adapter.get_setting(key) == read_declared_value(
            adapter.app_config, key
        ), key


# --- Agent persona block shape validation ---


def test_agents_block_is_a_known_top_level_group(caplog):
    """A configured ``agents`` group is not logged as an unknown group."""
    caplog.set_level("DEBUG")

    construct_app_config({"agents": {"architect": {"model": "m"}}})

    assert not any(
        "Ignoring unknown configuration group 'agents'" in message
        for message in caplog.messages
    )


def test_valid_agents_block_is_accepted():
    """A well-formed persona block leaves the typed view at its defaults."""
    assert (
        construct_app_config({"agents": {"architect": {"model": "m"}}})
        == DEFAULT_APP_CONFIG
    )


@pytest.mark.parametrize("value", ["architect", ["architect"], 5, True])
def test_non_mapping_agents_block_raises(value):
    """A scalar, sequence, or bool ``agents`` block fails naming the key."""
    with pytest.raises(ConfigurationError, match="agents"):
        construct_app_config({"agents": value})


@pytest.mark.parametrize("value", ["claude", ["claude"], 5])
def test_non_mapping_persona_entry_raises(value):
    """A persona entry that is not a mapping fails naming the persona key."""
    with pytest.raises(ConfigurationError, match="agents.architect"):
        construct_app_config({"agents": {"architect": value}})


def test_case_folded_duplicate_persona_keys_raise():
    """Two persona keys differing only in case fail, because order would decide."""
    with pytest.raises(ConfigurationError, match="agents"):
        construct_app_config(
            {"agents": {"Architect": {"model": "a"}, "architect": {"model": "b"}}}
        )
