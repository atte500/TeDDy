"""Unit coverage: preflight rejects a truthy ``llm.stream``.

Every ``llm.*`` key is forwarded verbatim to ``litellm.completion``, so a
truthy ``llm.stream`` yields a stream wrapper, the plan extraction finds no
``choices``, and the turn burns its retries on an empty plan. Preflight rejects
the key instead, accepting both a YAML boolean and the string that environment
interpolation produces.
"""

from typing import Any, Dict, List, Optional

import pytest

from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter
from teddy_executor.core.domain.models.exceptions import ConfigurationError
from tests.harness.setup.litellm_doubles import FakeLitellmProvider

_ABSENT = object()


def _configure(
    mock_config: Any,
    stream: Any = _ABSENT,
    api_key: str = "sk-test",  # pragma: allowlist secret
) -> None:
    settings: Dict[str, Any] = {"llm.model": "gpt-4o", "llm.api_key": api_key}
    if stream is not _ABSENT:
        settings["llm.stream"] = stream
    mock_config.get_setting.side_effect = lambda key, default=None: settings.get(
        key, default
    )


def _adapter(
    mock_config: Any, missing_keys: Optional[List[str]] = None
) -> LiteLLMAdapter:
    return LiteLLMAdapter(
        config_service=mock_config, _litellm_provider=FakeLitellmProvider(missing_keys)
    )


@pytest.mark.parametrize("stream_value", [True, "true"])
def test_validate_config_rejects_truthy_stream(mock_config, stream_value):
    _configure(mock_config, stream_value)

    errors = _adapter(mock_config).validate_config()

    assert len(errors) == 1, errors
    assert "llm.stream" in errors[0]
    assert "streaming" in errors[0].lower()
    assert "non-streamed" in errors[0].lower()


@pytest.mark.parametrize("stream_value", [False, "false", _ABSENT])
def test_validate_config_allows_falsy_or_absent_stream(mock_config, stream_value):
    _configure(mock_config, stream_value)

    errors = _adapter(mock_config).validate_config()

    assert errors == []


def test_truthy_stream_is_reported_alongside_missing_api_key(mock_config):
    _configure(mock_config, True, api_key="")

    errors = _adapter(mock_config, missing_keys=["OPENAI_API_KEY"]).validate_config()

    assert any("llm.stream" in error for error in errors), errors
    assert any("llm.api_key" in error for error in errors), errors


@pytest.mark.parametrize("stream_value", [True, "true"])
def test_truthy_stream_overlay_is_rejected_before_completion(
    mock_config, mock_time_service, stream_value
):
    """A persona-level stream reaches the merge guard before any request.

    ``get_completion`` is the boundary that receives the persona overlay, so a
    truthy flag here proves the backstop fires after preflight and before
    ``litellm.completion``. The provider double records every attempt, and the
    injected time service keeps the absent-guard Red run free of real sleeps.
    """
    _configure(mock_config)
    provider = FakeLitellmProvider()
    adapter = LiteLLMAdapter(
        config_service=mock_config,
        time_service=mock_time_service,
        _litellm_provider=provider,
    )

    with pytest.raises(ConfigurationError, match="llm.stream"):
        adapter.get_completion(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4o",
            llm_overrides={"stream": stream_value},
        )

    assert provider.completion_calls == []


@pytest.mark.parametrize("stream_value", [False, "false", _ABSENT])
def test_prepare_completion_params_allows_falsy_stream_overlay(
    mock_config, stream_value
):
    """A falsy or absent persona stream must not trigger the merge guard.

    The merge point is asserted directly because the provider double fails
    loudly on any completion; the property under test is that the guard stays
    keyed on truthiness, not that a request succeeds.
    """
    _configure(mock_config)
    adapter = _adapter(mock_config)
    overlay = {} if stream_value is _ABSENT else {"stream": stream_value}

    params = adapter._prepare_completion_params(model="gpt-4o", llm_overrides=overlay)

    assert params["model"] == "gpt-4o"
