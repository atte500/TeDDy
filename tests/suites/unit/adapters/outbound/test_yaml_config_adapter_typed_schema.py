"""Adapter-level coverage for the typed configuration schema.

The adapter validates declared values at load time and routes string lookups
through the typed view. Interpolation runs before schema construction, so a
``${VAR}`` token resolves to a real value before its declared type applies.
"""

import pytest

from teddy_executor.adapters.outbound.yaml_config_adapter import YamlConfigAdapter
from teddy_executor.core.domain.models.config_schema import (
    _SCHEMA_FIELDS,
    read_declared_value,
)
from teddy_executor.core.domain.models.exceptions import ConfigurationError


INTERPOLATED_ENV_NAME = "TEDDY_TEST_MAX_LINES"


def _write_config(tmp_path, body: str) -> None:
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir(parents=True, exist_ok=True)
    (teddy_dir / "config.yaml").write_text(body, encoding="utf-8")


def _write_env(tmp_path, body: str) -> None:
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir(parents=True, exist_ok=True)
    (teddy_dir / ".env").write_text(body, encoding="utf-8")


def _adapter(tmp_path) -> YamlConfigAdapter:
    return YamlConfigAdapter(config_path=".teddy/config.yaml", root_dir=str(tmp_path))


def test_absent_declared_key_resolves_the_schema_default(tmp_path):
    """A key missing from every layer resolves the single schema default."""
    adapter = _adapter(tmp_path)

    assert adapter.get_setting("execute.max_output_lines") == 100
    assert adapter.app_config.execute.max_output_lines == 100


def test_uncoercible_declared_value_is_rejected_at_load(tmp_path):
    """A wrong-typed declared value stops the load and names the key."""
    _write_config(tmp_path, 'execute:\n  max_output_lines: "one hundred"\n')

    with pytest.raises(ConfigurationError, match="execute.max_output_lines"):
        _adapter(tmp_path)


def test_out_of_range_declared_value_is_rejected_at_load(tmp_path):
    """A declared value outside its range stops the load and names the key."""
    _write_config(tmp_path, "edit:\n  similarity_threshold: 1.5\n")

    with pytest.raises(ConfigurationError, match="edit.similarity_threshold"):
        _adapter(tmp_path)


def test_unknown_group_is_tolerated_and_resolves_live(tmp_path):
    """An undeclared group does not fail the load and still reads live."""
    _write_config(tmp_path, "unknown_group:\n  foo: 1\n")

    adapter = _adapter(tmp_path)

    assert adapter.get_setting("unknown_group.foo") == 1


def test_interpolation_runs_before_schema_coercion(tmp_path, monkeypatch):
    """A ``${VAR}`` token resolves to a real value before its type applies."""
    monkeypatch.delenv(INTERPOLATED_ENV_NAME, raising=False)
    _write_config(
        tmp_path,
        f'execute:\n  max_output_lines: "${{{INTERPOLATED_ENV_NAME}}}"\n',
    )
    _write_env(tmp_path, f"{INTERPOLATED_ENV_NAME}=250\n")

    adapter = _adapter(tmp_path)

    assert adapter.get_setting("execute.max_output_lines") == 250
    assert adapter.app_config.execute.max_output_lines == 250


def test_get_setting_matches_the_typed_view_for_every_declared_key(tmp_path):
    """Every declared key keeps string lookup and typed access in parity."""
    adapter = _adapter(tmp_path)

    for spec in _SCHEMA_FIELDS:
        assert adapter.get_setting(spec.key) == read_declared_value(
            adapter.app_config, spec.key
        ), spec.key
