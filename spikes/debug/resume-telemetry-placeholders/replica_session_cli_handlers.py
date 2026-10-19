"""Replica of the resume meta synchronization helper with the candidate fix.

Only `_sync_and_display_session_meta` and its tiny echo helper are replicated.
The real session repository, session manager, and config service are used
through the injected container, so the rest of the behavior is unchanged.

The fix: removing `actual_model` marks the metadata dirty, so the clear is
persisted even when no model or api_key override is passed.
"""

from __future__ import annotations

import sys
from typing import Any, Optional

from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.ports.outbound.session_repository import ISessionRepository


def _echo_config_success(
    container: Any,
    agent: Optional[str] = None,
    model: Optional[str] = None,
) -> None:
    """Minimal identity echo; the production version writes richer output."""
    config_service: IConfigService = container.resolve(IConfigService)
    resolved_model = model or config_service.get_setting("llm.model", "unknown")
    identity_lines = []
    if agent:
        identity_lines.append(f"Agent: {agent}")
    identity_lines.append(f"Model: {resolved_model}")
    print("\n" + "\n".join(identity_lines), file=sys.stderr)


def _sync_and_display_session_meta(
    container: Any,
    session_name: str,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    agent: Optional[str] = None,
) -> None:
    """Replica with the candidate fix: a removed actual_model is a change."""
    session_manager: ISessionManager = container.resolve(ISessionManager)
    repository: ISessionRepository = container.resolve(ISessionRepository)
    config_service: IConfigService = container.resolve(IConfigService)

    latest_turn_path = session_manager.get_latest_turn(session_name)
    meta = repository.load_meta(latest_turn_path)

    changed = False
    # Clear actual_model so display falls through to current model (override or config).
    # Marking the clear as a change persists it even without an override.
    if "actual_model" in meta:
        meta.pop("actual_model", None)
        changed = True

    _echo_config_success(container, agent=agent or meta.get("agent_name"), model=model)

    config_model = config_service.get_setting("llm.model", "unknown")
    if model:
        meta["model"] = model
        changed = True
    elif config_model != "unknown" and meta.get("model") != config_model:
        meta["model"] = config_model
        changed = True
    if api_key:
        meta["api_key"] = api_key
        changed = True
    if changed:
        repository.save_meta(f"{latest_turn_path}/meta.yaml", meta)