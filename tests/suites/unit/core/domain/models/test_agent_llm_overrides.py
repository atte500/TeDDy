"""Contract coverage for the agent LLM overlay extractor.

``resolve_agent_llm_overrides`` returns the persona's configured ``llm``
overlay and an empty mapping when no matching persona is configured. Persona
matching is case-insensitive, matching the prompt resolver's casefold stem
rule. A blank ``model`` is dropped so it never reaches the provider as an
unresolvable model.
"""

import pytest

from teddy_executor.core.domain.models.config_schema import (
    resolve_agent_llm_overrides,
)


@pytest.mark.parametrize(
    "agents_block",
    [None, {}, {"pathfinder": {"model": "gpt"}}],
)
def test_absent_persona_yields_an_empty_overlay(agents_block):
    """No matching persona resolves to an empty overlay."""
    assert resolve_agent_llm_overrides(agents_block, "architect") == {}


def test_persona_block_is_returned_verbatim():
    """A configured persona block is returned with all of its keys intact."""
    block = {"model": "anthropic/claude", "api_key": "k", "timeout": 300}

    assert resolve_agent_llm_overrides({"architect": block}, "architect") == block


@pytest.mark.parametrize("declared_key", ["architect", "Architect", "ARCHITECT"])
def test_persona_match_is_case_insensitive(declared_key):
    """The persona key matches regardless of its declared casing."""
    overlay = resolve_agent_llm_overrides({declared_key: {"model": "m"}}, "architect")

    assert overlay == {"model": "m"}


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_blank_persona_model_is_dropped(blank):
    """A blank persona model is removed while the other keys survive."""
    overlay = resolve_agent_llm_overrides(
        {"architect": {"model": blank, "timeout": 300}}, "architect"
    )

    assert overlay == {"timeout": 300}


def test_non_mapping_agents_block_is_inert():
    """A malformed agents block yields an empty overlay at runtime."""
    assert resolve_agent_llm_overrides("architect", "architect") == {}


def test_non_mapping_persona_entry_is_inert():
    """A malformed persona entry yields an empty overlay at runtime."""
    assert resolve_agent_llm_overrides({"architect": "claude"}, "architect") == {}
