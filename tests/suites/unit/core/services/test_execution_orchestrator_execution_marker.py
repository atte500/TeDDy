"""Unit tests: a session turn records execution start before dispatching actions."""

from typing import cast
from unittest.mock import Mock

import pytest

from teddy_executor.core.domain.models import (
    ActionData,
    ActionLog,
    ActionStatus,
    Plan,
    RunStatus,
)
from teddy_executor.core.domain.models.orchestrator_ports import OrchestratorPorts
from teddy_executor.core.domain.models.plan import ValidationError
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser, InvalidPlanError
from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
from teddy_executor.core.ports.outbound import IFileSystemManager, IUserInteractor
from teddy_executor.core.ports.outbound.session_manager import EXECUTION_STARTED_MARKER
from teddy_executor.core.services.action_executor import ActionExecutor
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator
from teddy_executor.core.services.execution_report_assembler import (
    ExecutionReportAssembler,
)
from tests.harness.setup.mocking import to_posix_path

TURN_DIR = ".teddy/sessions/20260101_000000-marker/01"
PLAN_PATH = f"{TURN_DIR}/plan.md"
MARKER_PATH = f"{TURN_DIR}/{EXECUTION_STARTED_MARKER}"


def _execute_action() -> ActionData:
    return ActionData(type="EXECUTE", params={"command": "echo ok"})


def _session_plan() -> Plan:
    return Plan(
        title="Marked plan",
        rationale="Recording that execution began.",
        actions=[_execute_action()],
        is_session=True,
        plan_path=PLAN_PATH,
    )


def _stateless_plan() -> Plan:
    return Plan(
        title="Stateless plan",
        rationale="No session turn to mark.",
        actions=[_execute_action()],
    )


def _record_writes(events: list[tuple[str, ...]]) -> Mock:
    file_system = Mock(spec=IFileSystemManager)

    def record_write(path: str, content: str) -> None:
        events.append(("write", to_posix_path(path), content))

    file_system.write_file.side_effect = record_write
    return file_system


def _build_orchestrator(
    file_system: Mock,
    events: list[tuple[str, ...]],
    *,
    reviewer: IPlanReviewer | None = None,
    validation_errors: list[ValidationError] | None = None,
) -> ExecutionOrchestrator:
    validator = Mock(spec=IPlanValidator)
    validator.validate.return_value = list(validation_errors or [])

    def dispatch(action: ActionData, **_kwargs) -> tuple[ActionLog, str]:
        events.append(("dispatch", str(action.type)))
        return (
            ActionLog(
                status=ActionStatus.SUCCESS,
                action_type=str(action.type),
                params=dict(action.params),
                details="ok",
            ),
            "",
        )

    def skip(action: ActionData, reason: str) -> ActionLog:
        return ActionLog(
            status=ActionStatus.SKIPPED,
            action_type=str(action.type),
            params=dict(action.params),
            details=reason,
        )

    executor = Mock(spec=ActionExecutor)
    executor.reset_file_hashes.return_value = None
    executor.confirm_and_dispatch.side_effect = dispatch
    executor.handle_skipped_action.side_effect = skip

    return ExecutionOrchestrator(
        ports=OrchestratorPorts(
            plan_parser=cast(IPlanParser, Mock(spec=IPlanParser)),
            plan_validator=cast(IPlanValidator, validator),
            action_executor=cast(ActionExecutor, executor),
            file_system_manager=cast(IFileSystemManager, file_system),
            report_assembler=ExecutionReportAssembler(),
            user_interactor=cast(IUserInteractor, Mock(spec=IUserInteractor)),
            plan_reviewer=reviewer,
        )
    )


def test_session_plan_writes_marker_before_first_dispatch() -> None:
    events: list[tuple[str, ...]] = []
    orchestrator = _build_orchestrator(_record_writes(events), events)

    orchestrator.execute(plan=_session_plan(), require_approval=False)

    marker_writes = [
        index
        for index, event in enumerate(events)
        if event == ("write", MARKER_PATH, "")
    ]
    dispatches = [index for index, event in enumerate(events) if event[0] == "dispatch"]
    assert marker_writes == [0], events
    assert dispatches, events
    assert dispatches[0] > 0, events


def test_non_session_plan_writes_no_marker() -> None:
    events: list[tuple[str, ...]] = []
    orchestrator = _build_orchestrator(_record_writes(events), events)

    orchestrator.execute(plan=_stateless_plan(), require_approval=False)

    assert not [event for event in events if event[0] == "write"], events


def test_aborted_review_writes_no_marker() -> None:
    events: list[tuple[str, ...]] = []
    reviewer = Mock(spec=IPlanReviewer)
    reviewer.review.return_value = None
    orchestrator = _build_orchestrator(
        _record_writes(events), events, reviewer=reviewer
    )

    report = orchestrator.execute(plan=_session_plan(), require_approval=True)

    assert report.run_summary.status == RunStatus.ABORTED
    assert not [event for event in events if event[0] == "write"], events


def test_pre_flight_rejection_writes_no_marker() -> None:
    events: list[tuple[str, ...]] = []
    orchestrator = _build_orchestrator(
        _record_writes(events),
        events,
        validation_errors=[ValidationError(message="rejected before dispatch")],
    )

    with pytest.raises(InvalidPlanError):
        orchestrator.execute(plan=_session_plan(), require_approval=False)

    assert not [event for event in events if event[0] == "write"], events
