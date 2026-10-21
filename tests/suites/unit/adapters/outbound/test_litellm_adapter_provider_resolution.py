"""Unit coverage: preflight rejects a model with no resolvable provider.

A bare model name cannot be routed, so ``validate_config`` must fail early with
a paste-ready fix instead of deferring the failure to the first completion. The
failing resolution also prints the library provider list to stdout, which must
be captured so the CLI output stays clean.
"""

from unittest.mock import Mock

import pytest

from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter


@pytest.fixture
def adapter(mock_config):
    return LiteLLMAdapter(mock_config)


def _configure_model(mock_config, model, api_base=None):
    """Point the config double at a model, an optional api_base, and a present key."""
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "llm.api_key": "sk-present",  # pragma: allowlist secret
        "llm.model": model,
        "llm.api_base": api_base,
    }.get(key, default)


def test_validate_config_reports_unresolvable_model(adapter, mock_config, monkeypatch):
    """A bare model name surfaces a paste-ready provider error."""
    _configure_model(mock_config, "qwen3-coder-30b")

    import litellm

    monkeypatch.setattr(
        litellm, "validate_environment", Mock(return_value={"missing_keys": []})
    )
    monkeypatch.setattr(
        litellm,
        "get_llm_provider",
        Mock(side_effect=Exception("LLM Provider NOT provided")),
    )

    errors = adapter.validate_config()

    assert any(
        "Cannot infer a provider" in error
        and "qwen3-coder-30b" in error
        and "openai/qwen3-coder-30b" in error
        for error in errors
    ), errors


def test_validate_config_captures_provider_list_stdout(
    adapter, mock_config, monkeypatch, capsys
):
    """A failed resolution is reported without leaking the library provider list."""
    _configure_model(mock_config, "qwen3-coder-30b")

    import litellm

    monkeypatch.setattr(
        litellm, "validate_environment", Mock(return_value={"missing_keys": []})
    )

    def _fail_with_output(model, api_base=None, **kwargs):
        print("Provider List: https://docs.litellm.ai/docs/providers")
        raise Exception("LLM Provider NOT provided")

    monkeypatch.setattr(litellm, "get_llm_provider", _fail_with_output)

    errors = adapter.validate_config()

    captured = capsys.readouterr()
    assert any("Cannot infer a provider" in error for error in errors), errors
    assert "Provider List" not in captured.out, captured.out


def test_validate_config_skips_resolution_for_custom_api_base(
    adapter, mock_config, monkeypatch
):
    """A custom api_base is left to the user's endpoint, so no resolution runs."""
    _configure_model(
        mock_config, "qwen3-coder-30b", api_base="http://localhost:8080/v1"
    )

    import litellm

    monkeypatch.setattr(
        litellm, "validate_environment", Mock(return_value={"missing_keys": []})
    )
    monkeypatch.setattr(
        litellm,
        "get_llm_provider",
        Mock(side_effect=Exception("resolution must not run")),
    )

    errors = adapter.validate_config()

    assert not any("Cannot infer a provider" in error for error in errors), errors
