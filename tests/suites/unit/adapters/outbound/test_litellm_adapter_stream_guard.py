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

_ABSENT = object()


class _FakeLitellm:
    """Provider double: a clean environment and a resolvable model."""

    class AuthenticationError(Exception):
        pass

    def __init__(self, missing_keys: Optional[List[str]] = None) -> None:
        self._missing_keys = missing_keys or []

    def validate_environment(self, model: str) -> Dict[str, Any]:
        return {"missing_keys": list(self._missing_keys)}

    def get_llm_provider(self, model: str) -> Any:
        return ("openai", model, None, None)


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
        config_service=mock_config, _litellm_provider=_FakeLitellm(missing_keys)
    )


@pytest.mark.parametrize("stream_value", [True, "true"])
def test_validate_config_rejects_truthy_stream(mock_config, stream_value):
    _configure(mock_config, stream_value)

    errors = _adapter(mock_config).validate_config()

    assert len(errors) == 1, errors
    assert "llm.stream" in errors[0]
    assert "streaming" in errors[0].lower()
    assert "proxy" in errors[0].lower()


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
