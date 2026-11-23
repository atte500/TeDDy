"""Contract coverage for the effective-model precedence resolver.

``resolve_effective_model`` applies the slice precedence: the explicit flag
override wins, then the persona model, then the global ``llm.model``. A blank or
non-string candidate is skipped so an empty identifier never propagates to the
provider.
"""

import pytest

from teddy_executor.core.domain.models.config_schema import resolve_effective_model


def test_override_wins_over_persona_and_global():
    """The explicit flag outranks the persona and global models."""
    assert (
        resolve_effective_model("flag/model", "persona/model", "global/model")
        == "flag/model"
    )


def test_persona_wins_over_global_when_no_override():
    """Without a flag, the persona model outranks the global one."""
    assert (
        resolve_effective_model(None, "persona/model", "global/model")
        == "persona/model"
    )


def test_global_is_the_last_resort():
    """With no flag and no persona, the global model is used."""
    assert resolve_effective_model(None, None, "global/model") == "global/model"


@pytest.mark.parametrize("blank", ["", "   ", None, 5, []])
def test_blank_or_non_string_override_falls_through(blank):
    """A blank or non-string override is skipped, not propagated."""
    assert (
        resolve_effective_model(blank, "persona/model", "global/model")
        == "persona/model"
    )


def test_blank_persona_falls_back_to_global():
    """A blank persona model falls back to the global model."""
    assert resolve_effective_model("", "", "global/model") == "global/model"


def test_all_blank_returns_empty_string():
    """When every candidate is blank the resolver returns an empty string."""
    assert resolve_effective_model(None, "", "   ") == ""
