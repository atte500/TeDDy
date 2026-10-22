"""Typed configuration schema.

The schema declares the type and canonical default of every fixed
configuration key. It is an internal layer: the end-user ``config.yaml`` shape
is unchanged. Construction resolves each declared key with exact-flat-first
then nested precedence, coerces a safe string to its declared type, and falls
back to the schema default when a value is absent.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from teddy_executor.core.domain.models.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


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
    editor: str = ""
    yolo_default: bool = False


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


def _coerce_float(key: str, value: Any) -> float:
    """Coerce ``value`` to a ``float`` or raise a named configuration error."""
    expected = f"Configuration key '{key}' expected float, got {value!r}."
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            raise ConfigurationError(expected) from None
    raise ConfigurationError(expected)


_TRUE_TOKENS = frozenset({"true", "yes", "on"})
_FALSE_TOKENS = frozenset({"false", "no", "off"})


def _coerce_bool(key: str, value: Any) -> bool:
    """Coerce ``value`` to a ``bool`` or raise a named configuration error.

    Only real booleans and the documented ``true``/``false``, ``yes``/``no``,
    and ``on``/``off`` spellings are accepted, case-insensitively.
    """
    expected = f"Configuration key '{key}' expected bool, got {value!r}."
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        token = value.strip().lower()
        if token in _TRUE_TOKENS:
            return True
        if token in _FALSE_TOKENS:
            return False
    raise ConfigurationError(expected)


def _coerce_str(key: str, value: Any) -> str:
    """Coerce ``value`` to a ``str`` or raise a named configuration error."""
    if isinstance(value, str):
        return value
    raise ConfigurationError(f"Configuration key '{key}' expected str, got {value!r}.")


@dataclass(frozen=True)
class _FieldSpec:
    """Declares one configuration key, its typed target, and its valid range.

    ``group`` names the owning dataclass on ``AppConfig``. A ``None`` group
    marks a top-level scalar key that lives directly on ``AppConfig``. The
    ``minimum`` and ``maximum`` bounds are inclusive, and a ``None`` bound
    leaves that side unbounded, so a spec without bounds accepts any coercible
    value.
    """

    key: str
    group: str | None
    target: str
    kind: type
    minimum: float | None = None
    maximum: float | None = None


_SCHEMA_FIELDS: tuple[_FieldSpec, ...] = (
    _FieldSpec("editor", None, "editor", str),
    _FieldSpec(
        "execute.default_timeout_seconds",
        "execute",
        "default_timeout_seconds",
        float,
    ),
    _FieldSpec(
        "execute.max_output_lines", "execute", "max_output_lines", int, minimum=1
    ),
    _FieldSpec(
        "edit.similarity_threshold",
        "edit",
        "similarity_threshold",
        float,
        minimum=0.0,
        maximum=1.0,
    ),
    _FieldSpec("workspace.init", "workspace", "init", bool),
    _FieldSpec("workspace.pre-commit", "workspace", "pre_commit", bool),
    _FieldSpec("workspace.pull", "workspace", "pull", bool),
    _FieldSpec("read.max_lines", "read", "max_lines", int, minimum=1),
    _FieldSpec("context.max_tree_depth", "context", "max_tree_depth", int, minimum=0),
    _FieldSpec("research.max_results", "research", "max_results", int, minimum=1),
    _FieldSpec("checks.prompts", "checks", "prompts", bool),
    _FieldSpec("checks.templates", "checks", "templates", bool),
    _FieldSpec("checks.update", "checks", "update", bool),
    _FieldSpec("auto_pruning.enabled", "auto_pruning", "enabled", bool),
    _FieldSpec(
        "auto_pruning.turn_context_threshold",
        "auto_pruning",
        "turn_context_threshold",
        int,
    ),
    _FieldSpec(
        "auto_pruning.prune_failure_history",
        "auto_pruning",
        "prune_failure_history",
        bool,
    ),
    _FieldSpec(
        "auto_pruning.prune_validation_failures",
        "auto_pruning",
        "prune_validation_failures",
        bool,
    ),
    _FieldSpec(
        "auto_pruning.preserve_message_turns",
        "auto_pruning",
        "preserve_message_turns",
        bool,
    ),
    _FieldSpec(
        "auto_pruning.max_turns_retention",
        "auto_pruning",
        "max_turns_retention",
        int,
    ),
    _FieldSpec("guardrails.enabled", "guardrails", "enabled", bool),
    _FieldSpec("guardrails.max_turns", "guardrails", "max_turns", int),
    _FieldSpec("guardrails.max_session_cost", "guardrails", "max_session_cost", float),
    _FieldSpec("guardrails.message_reset", "guardrails", "message_reset", bool),
    _FieldSpec("yolo_default", None, "yolo_default", bool),
)

_DECLARED_KEY_TARGETS: dict[str, tuple[str | None, str]] = {
    spec.key: (spec.group, spec.target) for spec in _SCHEMA_FIELDS
}

_KNOWN_TOP_LEVEL = frozenset(
    {spec.group for spec in _SCHEMA_FIELDS if spec.group is not None}
    | {spec.key for spec in _SCHEMA_FIELDS if spec.group is None}
    | {"llm"}
)


def is_declared_key(key: str) -> bool:
    """Report whether ``key`` is a schema-declared configuration key."""
    return key in _DECLARED_KEY_TARGETS


def read_declared_value(config: AppConfig, key: str) -> Any:
    """Read the typed value of a declared ``key`` from ``config``.

    A declared value is always present, because construction fills every
    undeclared or empty value with its schema default.
    """
    assert is_declared_key(key), f"key {key!r} is not declared in the schema"
    group, target = _DECLARED_KEY_TARGETS[key]
    if group is None:
        return getattr(config, target)
    return getattr(getattr(config, group), target)


def _coerce(spec: _FieldSpec, value: Any) -> Any:
    """Coerce ``value`` to the declared type of ``spec``."""
    if spec.kind is bool:
        return _coerce_bool(spec.key, value)
    if spec.kind is int:
        return _coerce_int(spec.key, value)
    if spec.kind is str:
        return _coerce_str(spec.key, value)
    return _coerce_float(spec.key, value)


def _validate_range(spec: _FieldSpec, value: Any) -> Any:
    """Reject a value outside the declared inclusive bounds.

    The error names the key, the expected bound, and the offending value, so a
    user can correct the file from the message alone.
    """
    if spec.minimum is not None and value < spec.minimum:
        raise ConfigurationError(
            f"Configuration key '{spec.key}' expected a value of at least "
            f"{spec.minimum}, got {value!r}."
        )
    if spec.maximum is not None and value > spec.maximum:
        raise ConfigurationError(
            f"Configuration key '{spec.key}' expected a value of at most "
            f"{spec.maximum}, got {value!r}."
        )
    return value


def _log_unknown_keys(merged: Mapping[str, Any]) -> None:
    """Record each undeclared top-level group at debug level."""
    for key in merged:
        if key not in _KNOWN_TOP_LEVEL:
            logger.debug("Ignoring unknown configuration group %r", key)


def construct_app_config(merged: Mapping[str, Any]) -> AppConfig:
    """Build the typed configuration view from the merged config mapping.

    Each declared key resolves with exact-flat-first then nested precedence. A
    declared value coerces to its declared type, and an absent or empty value
    falls back to the schema default. An uncoercible value or a value outside
    its declared range raises a ``ConfigurationError`` naming the key.
    Undeclared top-level groups are ignored so future keys stay forward
    compatible.
    """
    _log_unknown_keys(merged)
    group_overrides: dict[str, dict[str, Any]] = {}
    top_level_overrides: dict[str, Any] = {}
    for spec in _SCHEMA_FIELDS:
        raw = _lookup(merged, spec.key)
        if raw is None or raw == "":
            continue
        coerced = _validate_range(spec, _coerce(spec, raw))
        if spec.group is None:
            top_level_overrides[spec.target] = coerced
        else:
            group_overrides.setdefault(spec.group, {})[spec.target] = coerced

    return AppConfig(
        execute=ExecuteConfig(**group_overrides.get("execute", {})),
        edit=EditConfig(**group_overrides.get("edit", {})),
        workspace=WorkspaceConfig(**group_overrides.get("workspace", {})),
        read=ReadConfig(**group_overrides.get("read", {})),
        context=ContextConfig(**group_overrides.get("context", {})),
        research=ResearchConfig(**group_overrides.get("research", {})),
        checks=ChecksConfig(**group_overrides.get("checks", {})),
        auto_pruning=AutoPruningConfig(**group_overrides.get("auto_pruning", {})),
        guardrails=GuardrailsConfig(**group_overrides.get("guardrails", {})),
        **top_level_overrides,
    )
