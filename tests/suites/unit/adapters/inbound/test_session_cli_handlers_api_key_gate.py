"""Unit tests for the API-key preflight gate helpers.

Pins the independent edge-case table for the two module-level helpers added by
the API-key preflight Seam:

* ``_is_llm_api_key_missing`` -- ``None`` / ``""`` / whitespace count as
  "missing"; a genuine (even padded) key counts as "present".
* ``_prompt_for_api_key`` -- a non-empty entry persists BOTH the env var and the
  ``${VAR}`` interpolation-form config key and prints the green confirmation;
  empty input and EOF/abort persist NOTHING and never raise.

These are helper-level tests. The higher-layer gate behaviour (whether the
prompt fires at all, keyed on ``setup_api_key`` plus the key's absence) is owned
by ``test_session_preflight_wiring.py``.
"""

from typing import Any, Optional

import pytest
import typer

from teddy_executor.adapters.inbound.session_cli_handlers import (
    _is_llm_api_key_missing,
    _prompt_for_api_key,
)
from teddy_executor.core.ports.outbound.config_service import IConfigService


class _RecordingConfigService(IConfigService):
    """In-memory ``IConfigService`` double recording persist calls.

    A real fake (not a mock) keeps the edge-case table free of mock-poisoning:
    the resolved ``llm.api_key`` is fixed at construction, and every
    ``set_env_variable`` / ``set_setting`` call is recorded for inspection.
    """

    def __init__(self, api_key: Optional[str]) -> None:
        self._api_key = api_key
        self.env_writes: list[tuple[str, str]] = []
        self.setting_writes: list[tuple[str, Any]] = []

    def get_config_path(self) -> str:
        return ".teddy/config.yaml"

    def get_setting(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        if key == "llm.api_key":
            return self._api_key
        return default

    def set_setting(self, key: str, value: Any) -> None:
        self.setting_writes.append((key, value))

    def set_env_variable(self, name: str, value: str) -> None:
        self.env_writes.append((name, value))


# --- _is_llm_api_key_missing: absent / blank permutations ------------------


@pytest.mark.parametrize("api_key", [None, "", "   ", "\t\n"])
def test_is_llm_api_key_missing_true_for_absent_or_blank(api_key):
    """A non-string, empty, or whitespace-only key counts as missing."""
    assert _is_llm_api_key_missing(_RecordingConfigService(api_key)) is True


@pytest.mark.parametrize("api_key", ["sk-real-key", "  sk-padded  "])
def test_is_llm_api_key_missing_false_for_genuine_key(api_key):
    """A genuine key (even with surrounding padding) counts as present."""
    assert _is_llm_api_key_missing(_RecordingConfigService(api_key)) is False


# --- _prompt_for_api_key: persist / no-persist permutations ----------------


def _capture_secho(monkeypatch):
    """Replace ``typer.secho`` with a recording callable; return the log."""
    messages: list[tuple[str, Any, Any]] = []

    def _record(message, fg=None, bold=None, err=None, **kwargs):
        messages.append((message, fg, err))

    monkeypatch.setattr("typer.secho", _record)
    return messages


def test_prompt_for_api_key_persists_both_forms_and_confirms(monkeypatch):
    """A non-empty entry persists the env var AND the ``${VAR}`` config form."""
    config = _RecordingConfigService(None)
    messages = _capture_secho(monkeypatch)
    monkeypatch.setattr("typer.prompt", lambda *a, **k: "sk-entered")

    _prompt_for_api_key(config)

    assert config.env_writes == [("TEDDY_LLM_API_KEY", "sk-entered")]
    assert config.setting_writes == [("llm.api_key", "${TEDDY_LLM_API_KEY}")]
    assert any(
        "saved to .teddy/.env" in message and fg == typer.colors.GREEN
        for message, fg, _ in messages
    )


def test_prompt_for_api_key_strips_surrounding_whitespace(monkeypatch):
    """The persisted key is the stripped entry, not the raw input."""
    config = _RecordingConfigService(None)
    monkeypatch.setattr("typer.secho", lambda *a, **k: None)
    monkeypatch.setattr("typer.prompt", lambda *a, **k: "  sk-entered  ")

    _prompt_for_api_key(config)

    assert config.env_writes == [("TEDDY_LLM_API_KEY", "sk-entered")]


@pytest.mark.parametrize("entry", ["", "   "])
def test_prompt_for_api_key_blank_input_persists_nothing(monkeypatch, entry):
    """Empty or whitespace-only input persists nothing."""
    config = _RecordingConfigService(None)
    monkeypatch.setattr("typer.secho", lambda *a, **k: None)
    monkeypatch.setattr("typer.prompt", lambda *a, **k: entry)

    _prompt_for_api_key(config)

    assert config.env_writes == []
    assert config.setting_writes == []


def test_prompt_for_api_key_eof_persists_nothing_without_raising(monkeypatch):
    """EOF (Ctrl-D) at the prompt persists nothing and does not raise."""
    config = _RecordingConfigService(None)
    monkeypatch.setattr("typer.secho", lambda *a, **k: None)

    def _raise_eof(*args, **kwargs):
        raise EOFError

    monkeypatch.setattr("typer.prompt", _raise_eof)

    _prompt_for_api_key(config)

    assert config.env_writes == []
    assert config.setting_writes == []


def test_prompt_for_api_key_abort_persists_nothing_without_raising(monkeypatch):
    """An aborted prompt persists nothing and does not raise."""
    config = _RecordingConfigService(None)
    monkeypatch.setattr("typer.secho", lambda *a, **k: None)

    def _raise_abort(*args, **kwargs):
        raise typer.Abort

    monkeypatch.setattr("typer.prompt", _raise_abort)

    _prompt_for_api_key(config)

    assert config.env_writes == []
    assert config.setting_writes == []
