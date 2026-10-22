"""Unit coverage for typed configuration schema construction.

Each declared key resolves with exact-flat-first then nested precedence. A
safe string coerces to the declared type, a missing value falls back to the
schema default, and an uncoercible value raises ``ConfigurationError`` naming
the key. The hyphenated ``workspace.pre-commit`` YAML key maps to the
``pre_commit`` Python field.
"""

import pytest

from teddy_executor.core.domain.models.config_schema import (
    DEFAULT_APP_CONFIG,
    construct_app_config,
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
