from datetime import datetime
import pytest
from teddy_executor.core.domain.models import (
    ActionData,
    ActionLog,
    ActionStatus,
    Plan,
    ReportAssemblyData,
    RunStatus,
)
from teddy_executor.core.services.execution_report_assembler import (
    ExecutionReportAssembler,
)


@pytest.fixture
def assembler():
    return ExecutionReportAssembler()


@pytest.fixture
def base_plan():
    return Plan(
        title="Test Plan",
        rationale="Test Rationale",
        actions=[ActionData(type="EXECUTE", params={})],
        metadata={"Agent": "TestAgent"},
    )


def test_assemble_success_status(assembler, base_plan):
    # Given action logs where at least one succeeded and none failed
    logs = [
        ActionLog(status=ActionStatus.SUCCESS, action_type="EXECUTE", params={}),
        ActionLog(status=ActionStatus.SKIPPED, action_type="EXECUTE", params={}),
    ]
    start_time = datetime.now()
    data = ReportAssemblyData(plan=base_plan, action_logs=logs, start_time=start_time)

    # When
    report = assembler.assemble(data)

    # Then
    assert report.run_summary.status == RunStatus.SUCCESS
    assert report.plan_title == base_plan.title
    assert report.action_logs == logs


def test_assemble_propagates_is_session_from_plan(assembler, base_plan):
    # Given a plan in session mode
    base_plan.is_session = True
    data = ReportAssemblyData(plan=base_plan, action_logs=[], start_time=datetime.now())

    # When
    report = assembler.assemble(data)

    # Then
    assert report.is_session is True


def test_assemble_propagates_explicit_is_session(assembler, base_plan):
    # Given an explicit session flag
    base_plan.is_session = False
    data = ReportAssemblyData(
        plan=base_plan, action_logs=[], start_time=datetime.now(), is_session=True
    )

    # When
    report = assembler.assemble(data)

    # Then
    assert report.is_session is True


def test_assemble_failure_status(assembler, base_plan):
    # Given any action failed
    logs = [
        ActionLog(status=ActionStatus.SUCCESS, action_type="EXECUTE", params={}),
        ActionLog(status=ActionStatus.FAILURE, action_type="EXECUTE", params={}),
    ]
    data = ReportAssemblyData(
        plan=base_plan, action_logs=logs, start_time=datetime.now()
    )

    # When
    report = assembler.assemble(data)

    # Then
    assert report.run_summary.status == RunStatus.FAILURE


def test_assemble_all_skipped_status(assembler, base_plan):
    # Given all actions were skipped
    logs = [
        ActionLog(status=ActionStatus.SKIPPED, action_type="EXECUTE", params={}),
        ActionLog(status=ActionStatus.SKIPPED, action_type="EXECUTE", params={}),
    ]
    data = ReportAssemblyData(
        plan=base_plan, action_logs=logs, start_time=datetime.now()
    )

    # When
    report = assembler.assemble(data)

    # Then
    assert report.run_summary.status == RunStatus.SKIPPED


def test_assemble_empty_logs_defaults_to_success(assembler, base_plan):
    # Given no actions were executed
    data = ReportAssemblyData(plan=base_plan, action_logs=[], start_time=datetime.now())

    # When
    report = assembler.assemble(data)

    # Then
    assert report.run_summary.status == RunStatus.SUCCESS


def test_assemble_preserves_user_request_metadata(assembler, base_plan):
    # Given metadata has user_request
    base_plan.metadata["user_request"] = "Custom Request"
    data = ReportAssemblyData(plan=base_plan, action_logs=[], start_time=datetime.now())

    # When
    report = assembler.assemble(data)

    # Then
    assert report.user_request == "Custom Request"


def test_assemble_prefers_explicit_message_over_metadata(assembler, base_plan):
    # Given both metadata and explicit message are provided
    base_plan.metadata["user_request"] = "Metadata Request"
    data = ReportAssemblyData(
        plan=base_plan,
        action_logs=[],
        start_time=datetime.now(),
        message="Explicit Message",
    )

    # When
    report = assembler.assemble(data)

    # Then
    assert report.user_request == "Explicit Message"
