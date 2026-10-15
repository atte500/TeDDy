"""Integration test: the TUI MESSAGE echo routes through the shared helper.

Slice 00-37 (User Message Terminal Echo), Migration deliverable.

When the TUI executes a MESSAGE action, ``orchestrate_execution`` echoes the
user's typed reply under the canonical "User Message:" label. That echo MUST
route through the shared ``emit_user_message`` helper so the terminal-echo
format stays single-sourced across the initial-request, post-execution, and
TUI paths.
"""

import asyncio
from types import SimpleNamespace

from teddy_executor.adapters.inbound import textual_plan_reviewer_execution
from teddy_executor.core.domain.models.execution_report import ActionLog, ActionStatus
from teddy_executor.core.domain.models.plan import ActionData


class _RecordingDispatcher:
    """In-memory fake of the action dispatcher returning a canned log."""

    def __init__(self, log: ActionLog) -> None:
        self._log = log
        self.dispatched: list[ActionData] = []

    def dispatch_and_execute(self, action: ActionData) -> ActionLog:
        self.dispatched.append(action)
        return self._log


def _build_app(log: ActionLog) -> SimpleNamespace:
    """Minimal stand-in for ``ReviewerApp`` exposing only the execution seams."""
    return SimpleNamespace(
        INSTRUCTION_MARKER="<!-- marker -->",
        _action_dispatcher=_RecordingDispatcher(log),
        _refresh_node=lambda node: None,
        refresh_bindings=lambda: None,
    )


def test_orchestrate_execution_routes_message_echo_through_emit_user_message(
    monkeypatch,
) -> None:
    """The TUI MESSAGE echo must call ``emit_user_message`` with the reply."""
    echoed: list[str] = []
    monkeypatch.setattr(
        textual_plan_reviewer_execution,
        "emit_user_message",
        lambda content: echoed.append(content),
        raising=False,
    )

    action = ActionData(type="MESSAGE", params={})
    log = ActionLog(
        status=ActionStatus.SUCCESS,
        action_type="MESSAGE",
        params={},
        details="Typed reply from TUI",
    )
    app = _build_app(log)
    node = SimpleNamespace(data=action)

    asyncio.run(
        textual_plan_reviewer_execution.orchestrate_execution(
            app, node, lambda a, act: None
        )
    )

    assert echoed == ["Typed reply from TUI"], (
        "The TUI MESSAGE echo must route through the shared emit_user_message "
        "helper so the terminal-echo format stays single-sourced across the "
        "initial-request, post-execution, and TUI paths."
    )
