"""Integration test: manual TUI execution records the action's sequence.

Slice 04-12 (Truthful Execution Order), Core deliverable.

Running a single action by hand in the reviewer must stamp it at the moment it
runs, using the shared Plan.next_execution_sequence rule. Otherwise the
orchestrator's pre-loop fallback numbers hand-executed actions in plan order,
and both the console prelude and the report claim an order that never happened.
"""

import asyncio
from types import SimpleNamespace

from teddy_executor.adapters.inbound.textual_plan_reviewer_execution import (
    orchestrate_execution,
)
from teddy_executor.core.domain.models.execution_report import ActionLog, ActionStatus
from teddy_executor.core.domain.models.plan import ActionData, Plan


class _StubDispatcher:
    """In-memory fake returning a success log for the dispatched action."""

    def dispatch_and_execute(self, action: ActionData) -> ActionLog:
        return ActionLog(
            status=ActionStatus.SUCCESS,
            action_type=action.type,
            params=action.params,
        )


def _build_app(plan: Plan) -> SimpleNamespace:
    """Minimal stand-in for ReviewerApp exposing only the execution seams."""
    return SimpleNamespace(
        INSTRUCTION_MARKER="<!-- marker -->",
        plan=plan,
        _action_dispatcher=_StubDispatcher(),
        _refresh_node=lambda node: None,
        refresh_bindings=lambda: None,
    )


def _run_manually(app: SimpleNamespace, action: ActionData) -> None:
    """Executes one action through the reviewer's manual path."""
    node = SimpleNamespace(data=action)
    asyncio.run(orchestrate_execution(app, node, lambda a, act: None))


def test_manual_execution_records_the_first_sequence() -> None:
    """A hand-executed action carries the first sequence number."""
    action = ActionData(type="EXECUTE", params={"command": "ls"})
    plan = Plan(title="Manual", rationale="Test", actions=[action])

    _run_manually(_build_app(plan), action)

    assert action.execution_sequence == 1


def test_manual_executions_record_the_order_they_actually_ran() -> None:
    """Two hand-executed actions are numbered by run order, not plan order."""
    first_in_plan = ActionData(type="EXECUTE", params={"command": "first"})
    second_in_plan = ActionData(type="EXECUTE", params={"command": "second"})
    plan = Plan(
        title="Manual Order",
        rationale="Test",
        actions=[first_in_plan, second_in_plan],
    )
    app = _build_app(plan)

    _run_manually(app, second_in_plan)
    _run_manually(app, first_in_plan)

    assert second_in_plan.execution_sequence == 1
    assert first_in_plan.execution_sequence == 2
