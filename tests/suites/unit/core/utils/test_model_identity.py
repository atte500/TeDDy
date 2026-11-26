from typing import Optional

import pytest

from teddy_executor.core.utils.model_identity import split_model_identity


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        (
            "openrouter/~deepseek/deepseek-flash-latest",
            ("~deepseek/deepseek-flash-latest", "openrouter"),
        ),
        (
            "openrouter/deepseek/deepseek-flash-latest",
            ("deepseek/deepseek-flash-latest", "openrouter"),
        ),
        ("deepseek-chat", ("deepseek-chat", "unknown")),
        ("", ("Unknown", "unknown")),
        (None, ("Unknown", "unknown")),
    ],
)
def test_the_identity_splits_the_leading_provider_segment(
    model: Optional[str], expected: tuple[str, str]
):
    """LiteLLM provider prefixes are optional, so a bare model has no provider."""
    assert split_model_identity(model) == expected
