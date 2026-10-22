"""Typed configuration schema.

The schema declares the type and canonical default of every fixed
configuration key. It is an internal layer: the end-user ``config.yaml`` shape
is unchanged. The initial skeleton validates only the EXECUTE output cap; the
full per-key construction lands in later deliverables.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from teddy_executor.core.domain.models.exceptions import ConfigurationError


@dataclass(frozen=True)
class ExecuteConfig:
    default_timeout_seconds: float = 60.0
    max_output_lines: int = 100


@dataclass(frozen=True)
class EditConfig:
    similarity_threshold: float = 0.95


@dataclass(frozen=True)
class WorkspaceConfig:
    init: bool = True
    pre_commit: bool = True
    pull: bool = True


@dataclass(frozen=True)
class ReadConfig:
    max_lines: int = 1000


@dataclass(frozen=True)
class ContextConfig:
    max_tree_depth: int = 4


@dataclass(frozen=True)
class ResearchConfig:
    max_results: int = 5


@dataclass(frozen=True)
class ChecksConfig:
    prompts: bool = True
    templates: bool = True
    update: bool = True


@dataclass(frozen=True)
class AutoPruningConfig:
    enabled: bool = True
    turn_context_threshold: int = 50000
    prune_failure_history: bool = True
    prune_validation_failures: bool = True
    preserve_message_turns: bool = True
    max_turns_retention: int = 10


@dataclass(frozen=True)
class GuardrailsConfig:
    enabled: bool = True
    max_turns: int = 150
    max_session_cost: float = 5.0
    message_reset: bool = True


@dataclass(frozen=True)
class AppConfig:
    execute: ExecuteConfig = field(default_factory=ExecuteConfig)
    edit: EditConfig = field(default_factory=EditConfig)
    workspace: WorkspaceConfig = field(default_factory=WorkspaceConfig)
    read: ReadConfig = field(default_factory=ReadConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    research: ResearchConfig = field(default_factory=ResearchConfig)
    checks: ChecksConfig = field(default_factory=ChecksConfig)
    auto_pruning: AutoPruningConfig = field(default_factory=AutoPruningConfig)
    guardrails: GuardrailsConfig = field(default_factory=GuardrailsConfig)


DEFAULT_APP_CONFIG = AppConfig()


def _lookup(merged: Mapping[str, Any], key: str) -> Any:
    """Resolve ``key`` with exact-flat-first then nested precedence.

    ``get_setting`` treats a top-level dotted key as a higher priority than the
    nested path. The schema mirrors that order so typed access and string access
    stay in parity.
    """
    if key in merged:
        return merged[key]
    current: Any = merged
    for part in key.split("."):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        else:
            return None
    return current


def _coerce_int(key: str, value: Any) -> int:
    """Coerce ``value`` to an ``int`` or raise a named configuration error."""
    expected = f"Configuration key '{key}' expected int, got {value!r}."
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            raise ConfigurationError(expected) from None
    raise ConfigurationError(expected)


def construct_app_config(merged: Mapping[str, Any]) -> AppConfig:
    """Build the typed configuration view from the merged config mapping.

    Skeleton: resolves and validates only ``execute.max_output_lines``. Every
    other field falls back to ``DEFAULT_APP_CONFIG`` until the full per-key
    construction lands in the next deliverable.
    """
    raw = _lookup(merged, "execute.max_output_lines")
    if raw is not None:
        _coerce_int("execute.max_output_lines", raw)
    return DEFAULT_APP_CONFIG
