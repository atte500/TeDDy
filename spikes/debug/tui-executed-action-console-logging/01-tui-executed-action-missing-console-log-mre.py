"""MRE: actions pre-executed via TUI 'x' are not logged to console on submit.

A pre-executed ActionData (executed=True + cached action_log) is processed by
ExecutionOrchestrator WITHOUT emitting the console log lines that
ActionDispatcher emits for a freshly dispatched action ("CREATE - desc" /
"SUCCESS").

Run: uv run python spikes/debug/tui-executed-action-console-logging/01-tui-executed-action-missing-console-log-mre.py
"""
from __future__ import annotations

import io
import logging
import traceback

from teddy_executor.core.domain.models import (
    ActionData,
    ActionLog,
    ActionStatus,
    Plan,
)
from teddy_executor.core.domain.models.orchestrator_ports import OrchestratorPorts
from teddy_executor.core.services.action_dispatcher import ActionDispatcher
from replica_execution_orchestrator import ExecutionOrchestrator
from teddy_executor.core.services.execution_report_assembler import (
    ExecutionReportAssembler,
)


class _Stub:
    """Minimal attribute bag (no external mock libraries)."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class _Handler:
    def execute(self, **_kwargs):
        return "ok"


class _Factory:
    def create_action(self, _action_type, _params=None):
        return _Handler()


def _capture(fn):
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger()
    old_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    try:
        fn()
    except Exception:
        traceback.print_exc()
    finally:
        root.removeHandler(handler)
        root.setLevel(old_level)
    return stream.getvalue()


def _build_orchestrator() -> ExecutionOrchestrator:
    validator = _Stub(validate=lambda _plan: [])

    def _skip(action, reason):
        return ActionLog(
            status=ActionStatus.SKIPPED,
            action_type=action.type,
            params=action.params,
            details=reason,
        )

    executor = _Stub(reset_file_hashes=lambda: None, handle_skipped_action=_skip)
    return ExecutionOrchestrator(
        ports=OrchestratorPorts(
            plan_parser=_Stub(parse=lambda *_a, **_k: None),
            plan_validator=validator,
            action_executor=executor,
            file_system_manager=_Stub(),
            report_assembler=ExecutionReportAssembler(),
            user_interactor=_Stub(),
        )
    )


def scenario_preexecuted() -> None:
    """Submitted-plan path for an action already executed via TUI 'x'."""
    persisted = ActionLog(
        status=ActionStatus.SUCCESS,
        action_type="CREATE",
        params={"path": "pre.txt"},
    )
    action = ActionData(
        type="CREATE",
        params={"path": "pre.txt"},
        description="created manually via x",
        executed=True,
        action_log=persisted,
    )
    plan = Plan(title="MRE", rationale="r", actions=[action])
    _build_orchestrator().execute(plan=plan, interactive=False)


def scenario_fresh() -> None:
    """Reference: a freshly dispatched action logs its console lines."""
    dispatcher = ActionDispatcher(_Factory())
    action = ActionData(
        type="CREATE",
        params={"path": "fresh.txt"},
        description="fresh action",
    )
    dispatcher.dispatch_and_execute(action)


def main() -> None:
    pre = _capture(scenario_preexecuted)
    fresh = _capture(scenario_fresh)

    print("=== PRE-EXECUTED action capture (submit path) ===")
    print(pre if pre.strip() else "<EMPTY>")
    print("=== FRESH action capture (dispatch path) ===")
    print(fresh if fresh.strip() else "<EMPTY>")

    fresh_ok = "CREATE" in fresh and "SUCCESS" in fresh
    pre_present = "CREATE" in pre and "SUCCESS" in pre
    if fresh_ok and pre_present:
        print("RESULT: PASS -- FIX PROVEN (pre-executed action now logs on submit)")
    else:
        print("RESULT: FAIL -- pre-executed action still silent")


if __name__ == "__main__":
    main()