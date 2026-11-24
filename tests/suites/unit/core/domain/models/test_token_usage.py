import dataclasses

import pytest

from teddy_executor.core.domain.models import TokenUsage
from teddy_executor.core.domain.models.token_usage import TokenUsage as DirectTokenUsage


def test_token_usage_defaults_to_zero_counters():
    assert TokenUsage() == TokenUsage(prompt_tokens=0, cached_tokens=0)


def test_token_usage_is_re_exported_from_the_models_package():
    assert TokenUsage is DirectTokenUsage


def test_token_usage_is_immutable():
    usage = TokenUsage()

    with pytest.raises(dataclasses.FrozenInstanceError):
        usage.cached_tokens = 5


def test_token_usage_compares_by_value():
    assert TokenUsage(10, 4) == TokenUsage(10, 4)
    assert TokenUsage(10, 4) != TokenUsage(10, 5)
