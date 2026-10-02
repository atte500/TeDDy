"""Unit tests: interrupt drain in ExecutionOrchestrator._process_plan_actions.

Two-phase Ctrl+C semantics: after an action completes, a set
`interrupted` flag on the injected InterruptGuard must drain the plan —
every remaining action is skipped via the action executor with the
interrupt reason and the loop exits normally, so the report assembler
receives the FULL audit trail (real logs for completed actions +
interrupt skips for the rest) and the session-loop boundary's existing
finalize path generates report.md. Without an interrupt the loop
dispatches every action as before.
"""

import time
from collections.abc import Callable
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

from teddy_executor.core.domain.models import (
    ActionData,
    ActionLog,
    ActionStatus,
    ExecutionReport,
    Plan,
)
from teddy_executor.core.domain.models.orchestrator_ports import OrchestratorPorts
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.execution_report_assembler import (
    IExecutionReportAssembler,
)
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.services.action_executor import ActionExecutor
from teddy_executor.core.services.execution_orchestrator import (
    INTERRUPT_REASON,
    ExecutionOrchestrator,
)
from teddy_executor.core.utils.interrupt_guard import InterruptGuard


def _real_guard() -> InterruptGuard:
    """A REAL guard over a spec-bound config double (core logic stays real)."""
    config = Mock(spec=IConfigService)
    config.get_setting.return_value = 2.0
    return InterruptGuard(config_service=config, monotonic=time.monotonic)


def _build_orchestrator(
    guard: InterruptGuard,
    dispatch: Callable[..., tuple[ActionLog, str]],
) -> SimpleNamespace:
    """ExecutionOrchestrator over spec-bound doubles with the REAL guard.

    The dispatch callable is installed as confirm_and_dispatch's
    side_effect (it decides per scenario whether/when to set the drain
    flag); handle_skipped_action constructs real SKIPPED logs captured in
    skip_logs so identity assertions observe the exact objects the drain
    delivered to the assembler.
    """
    validator = Mock(spec=IPlanValidator)
    validator.validate.return_value = []

    executor = Mock(spec=ActionExecutor)
    executor.confirm_and_dispatch.side_effect = dispatch
    skip_logs: list[ActionLog] = []

    def make_skip_log(action: ActionData, reason: str) -> ActionLog:
        log = ActionLog(
            status=ActionStatus.SKIPPED,
            action_type=action.type,
            params=dict(action.params),
            details=reason,
        )
        skip_logs.append(log)
        return log

    executor.handle_skipped_action.side_effect = make_skip_log

    assembler = Mock(spec=IExecutionReportAssembler)
    assembler.assemble.return_value = Mock(spec=ExecutionReport)

    orchestrator = ExecutionOrchestrator(
        ports=OrchestratorPorts(
            plan_parser=cast(IPlanParser, Mock(spec=IPlanParser)),
            plan_validator=cast(IPlanValidator, validator),
            action_executor=executor,
            file_system_manager=cast(IFileSystemManager, Mock(spec=IFileSystemManager)),
            report_assembler=assembler,
            user_interactor=cast(IUserInteractor, Mock(spec=IUserInteractor)),
            interrupt_guard=guard,
        )
    )
    return SimpleNamespace(
        orchestrator=orchestrator,
        executor=executor,
        assembler=assembler,
        skip_logs=skip_logs,
    )


class TestInterruptDrain:
    """A set interrupted flag after an action drains the remaining plan."""

    def test_interrupted_flag_skips_remaining_actions_with_interrupt_reason(self):
        # Arrange: the signal "arrives" during action 1's dispatch — the
        # drain flag is set while the in-flight action executes.
        guard = _real_guard()
        success_log = ActionLog(
            status=ActionStatus.SUCCESS,
            action_type="EXECUTE",
            params={"command": "cmd0"},
            details="ok",
        )

        def dispatch(action, **kwargs):
            guard.interrupted.set()
            return success_log, ""

        h = _build_orchestrator(guard, dispatch)
        actions = [
            ActionData(type="EXECUTE", params={"command": f"cmd{i}"}) for i in range(3)
        ]
        plan = Plan(title="Interrupted Plan", rationale="test", actions=actions)

        # Act
        h.orchestrator.execute(plan=plan, interactive=False)

        # Assert: only the in-flight action was dispatched; the drain
        # skipped the remaining actions with the interrupt reason, and the
        # assembler received the full audit trail (1 real + 2 skip logs).
        h.executor.confirm_and_dispatch.assert_called_once()
        skip_calls = h.executor.handle_skipped_action.call_args_list
        assert [call.args[0] for call in skip_calls] == [actions[1], actions[2]]
        assert all(call.args[1] == INTERRUPT_REASON for call in skip_calls)
        assembled = h.assembler.assemble.call_args.args[0].action_logs
        assert assembled[0] is success_log
        assert assembled[1] is h.skip_logs[0]
        assert assembled[2] is h.skip_logs[1]
        assert all(log.status == ActionStatus.SKIPPED for log in assembled[1:])

    def test_interrupt_during_second_action_drains_only_later_actions(self):
        # Arrange: the flag is set while action 2 is in flight — actions 1
        # and 2 complete and log normally; only action 3 is skipped.
        guard = _real_guard()
        dispatched: list[ActionLog] = []

        def dispatch(action, **kwargs):
            if len(dispatched) == 1:
                guard.interrupted.set()
            log = ActionLog(
                status=ActionStatus.SUCCESS,
                action_type="EXECUTE",
                params=dict(action.params),
                details="ok",
            )
            dispatched.append(log)
            return log, ""

        h = _build_orchestrator(guard, dispatch)
        actions = [
            ActionData(type="EXECUTE", params={"command": f"cmd{i}"}) for i in range(3)
        ]
        plan = Plan(title="Mid-Plan Interrupt", rationale="test", actions=actions)

        # Act
        h.orchestrator.execute(plan=plan, interactive=False)

        # Assert: the two in-flight actions dispatched and logged; the
        # drain skipped only the action AFTER the flag was set.
        assert h.executor.confirm_and_dispatch.call_count == 2
        skip_calls = h.executor.handle_skipped_action.call_args_list
        assert [call.args[0] for call in skip_calls] == [actions[2]]
        assert skip_calls[0].args[1] == INTERRUPT_REASON
        assembled = h.assembler.assemble.call_args.args[0].action_logs
        assert assembled[0] is dispatched[0]
        assert assembled[1] is dispatched[1]
        assert assembled[2] is h.skip_logs[0]
        assert assembled[2].status == ActionStatus.SKIPPED

    def test_no_interrupt_dispatches_every_action(self):
        # Arrange: no signal ever arrives — the control proves the drain
        # check is inert when the flag stays unset.
        guard = _real_guard()
        dispatched: list[ActionLog] = []

        def dispatch(action, **kwargs):
            log = ActionLog(
                status=ActionStatus.SUCCESS,
                action_type="EXECUTE",
                params=dict(action.params),
                details="ok",
            )
            dispatched.append(log)
            return log, ""

        h = _build_orchestrator(guard, dispatch)
        actions = [
            ActionData(type="EXECUTE", params={"command": f"cmd{i}"}) for i in range(3)
        ]
        plan = Plan(title="Uninterrupted Plan", rationale="test", actions=actions)

        # Act
        h.orchestrator.execute(plan=plan, interactive=False)

        # Assert: every action dispatched; no skips; the assembler
        # received the dispatched logs by identity, all SUCCESS.
        assert h.executor.confirm_and_dispatch.call_count == 3
        h.executor.handle_skipped_action.assert_not_called()
        assembled = h.assembler.assemble.call_args.args[0].action_logs
        assert all(a is d for a, d in zip(assembled, dispatched))
        assert all(log.status == ActionStatus.SUCCESS for log in assembled)


def test_interrupt_reason_is_the_reworded_notice():
    """The drain reason must carry the reworded notice (Bug 56 rewording).

    The reason is the single shared interrupt notice; the now-inaccurate
    "(Ctrl+C)" fragment was dropped so it matches the boundary notice.
    """
    assert INTERRUPT_REASON == "Interrupted by user."
