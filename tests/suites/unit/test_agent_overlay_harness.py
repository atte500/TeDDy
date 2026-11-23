"""Harness coverage for the per-persona LLM overlay doubles.

The shared LLM double is bound to ``ILlmClient``, so it must accept the additive
``llm_overrides`` keyword and record it. The real ``YamlConfigAdapter`` is the
persona-capable config path: it resolves an undeclared ``agents.<persona>`` block
through its live walk, and ``resolve_agent_llm_overrides`` extracts the overlay
from it, alongside the still-applied global ``llm`` defaults.
"""

import pytest

from teddy_executor.adapters.outbound.yaml_config_adapter import YamlConfigAdapter
from teddy_executor.core.domain.models.config_schema import (
    resolve_agent_llm_overrides,
)
from teddy_executor.core.domain.models.exceptions import ConfigurationError


def test_llm_double_accepts_the_overlay_keyword(mock_llm_client):
    """The spec-bound LLM double records an overlay passed by keyword."""
    messages = [{"role": "user", "content": "hi"}]

    mock_llm_client.get_completion(
        messages=messages,
        model="anthropic/claude",
        llm_overrides={"timeout": 300},
    )

    mock_llm_client.get_completion.assert_called_once_with(
        messages=messages,
        model="anthropic/claude",
        llm_overrides={"timeout": 300},
    )


def _write_config(tmp_path, body: str) -> YamlConfigAdapter:
    """Build a real adapter over a hermetic ``.teddy/config.yaml``."""
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir()
    (teddy_dir / "config.yaml").write_text(body, encoding="utf-8")
    return YamlConfigAdapter(config_path=".teddy/config.yaml", root_dir=str(tmp_path))


def test_real_config_resolves_a_persona_overlay(tmp_path):
    """The real adapter walks ``agents.<persona>`` and the extractor reads it."""
    adapter = _write_config(
        tmp_path,
        "agents:\n"
        "  architect:\n"
        '    model: "anthropic/claude-sonnet-4-5"\n'
        "    timeout: 300\n",
    )

    block = adapter.get_setting("agents.architect")

    assert resolve_agent_llm_overrides({"architect": block}, "architect") == {
        "model": "anthropic/claude-sonnet-4-5",
        "timeout": 300,
    }


def test_persona_block_coexists_with_the_global_llm_block(tmp_path):
    """A persona overlay resolves while the global ``llm`` defaults still apply."""
    adapter = _write_config(
        tmp_path,
        'agents:\n  architect:\n    model: "anthropic/claude-sonnet-4-5"\n',
    )

    assert adapter.get_setting("llm.timeout") == 300
    assert resolve_agent_llm_overrides(
        {"architect": adapter.get_setting("agents.architect")}, "architect"
    ) == {"model": "anthropic/claude-sonnet-4-5"}


def test_malformed_agents_block_fails_at_load(tmp_path):
    """The real adapter rejects a scalar ``agents`` block through the schema."""
    with pytest.raises(ConfigurationError, match="agents"):
        _write_config(tmp_path, 'agents: "architect"\n')


def test_empty_persona_entry_loads_as_a_declared_persona(tmp_path):
    """A bare persona key declares the persona with no overrides."""
    adapter = _write_config(tmp_path, "agents:\n  architect:\n")

    assert adapter.get_setting("llm.timeout") == 300


def test_scalar_persona_entry_still_fails_at_load(tmp_path):
    """A non-empty non-mapping persona entry still fails naming the persona."""
    with pytest.raises(ConfigurationError, match="agents.architect"):
        _write_config(tmp_path, 'agents:\n  architect: "claude"\n')


def test_bundled_defaults_load_under_a_minimal_user_config(tmp_path):
    """The shipped bundled config validates with no persona overrides set."""
    adapter = _write_config(tmp_path, "yolo_default: false\n")

    assert adapter.get_setting("llm.timeout") == 300
