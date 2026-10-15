"""MRE for the resume `-a/--agent` display bug.

`teddy resume -a prototyper` shows the session's STORED agent in the identity
banner instead of the requested override.

This drives the real `handle_resume_session` entry point with a mock container
and captures the emitted banner. Run:

    uv run python spikes/debug/resume-agent-override/01-agent-override-display-mre.py

Exit codes: 0 = override displayed (fixed), 1 = bug reproduced, 2 = inconclusive.
"""

from __future__ import annotations

import contextlib
import io
from unittest.mock import MagicMock  # noqa: TID251

from teddy_executor.adapters.inbound import session_cli_handlers as handlers
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.ports.outbound.session_repository import ISessionRepository

STORED_AGENT = "pathfinder"
OVERRIDE_AGENT = "prototyper"


def build_container() -> MagicMock:
    """Build a mock container with the minimal services the resume path needs."""
    container = MagicMock()
    session_manager = MagicMock(spec=ISessionManager)
    repository = MagicMock(spec=ISessionRepository)
    config = MagicMock(spec=IConfigService)

    session_manager.resolve_session_from_path.return_value = "20260101_000000-derisk"
    session_manager.get_latest_turn.return_value = (
        ".teddy/sessions/20260101_000000-derisk/01"
    )
    session_manager.get_cumulative_cost.return_value = 0.0

    repository.load_meta.return_value = {
        "agent_name": STORED_AGENT,
        "model": "openrouter/stored-model",
    }

    config.get_setting.side_effect = lambda key, default=None: {
        "llm.model": "openrouter/config-model",
        "checks.update": False,
        "checks.prompts": False,
        "checks.templates": False,
    }.get(key, default)

    container.resolve.side_effect = lambda cls, **kw: {
        ISessionManager: session_manager,
        ISessionRepository: repository,
        IConfigService: config,
    }.get(cls, MagicMock())
    return container


def main() -> int:
    container = build_container()

    # Neutralize side-effecting / network boundaries for a fast, deterministic run.
    handlers.background_check = lambda *a, **k: None
    handlers._display_update_notification = lambda *a, **k: []
    handlers._run_health_checks = lambda *a, **k: None
    handlers._run_cli_preflight_check = lambda *a, **k: []
    handlers._orchestrate_session_loop = lambda *a, **k: None

    buf = io.StringIO()
    raised: Exception | None = None
    try:
        with contextlib.redirect_stderr(buf), contextlib.redirect_stdout(buf):
            handlers.handle_resume_session(
                container=container,
                path="derisk",
                interactive=False,
                no_copy=True,
                agent=OVERRIDE_AGENT,
            )
    except Exception as exc:  # noqa: BLE001 - MRE diagnostic boundary
        raised = exc

    output = buf.getvalue()
    print("---- captured banner ----")
    print(output)
    print("-------------------------")
    if raised is not None:
        print(f"[handler raised: {raised!r}]")

    expected = "Agent: Prototyper"
    buggy = "Agent: Pathfinder"
    if expected in output:
        print(f"PASS: override displayed ({expected!r})")
        return 0
    if buggy in output:
        print(f"FAIL (bug reproduced): displayed {buggy!r} instead of {expected!r}")
        return 1
    print("INCONCLUSIVE: no agent line captured")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())