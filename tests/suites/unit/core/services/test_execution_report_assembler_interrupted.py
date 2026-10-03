"""Unit tests: ExecutionReportAssembler folds INTERRUPTED into the overall run
status (Bug 58 Option B).

A purely-interrupted plan must NOT report SUCCESS; the derivation priority is
FAILURE > INTERRUPTED > SUCCESS > SKIPPED.
"""

from teddy_executor.core.domain.models import ActionLog, ActionStatus, RunStatus
from teddy_executor.core.services.execution_report_assembler import (
    ExecutionReportAssembler,
)


def _log(status: ActionStatus) -> ActionLog:
    return ActionLog(status=status, action_type="EXECUTE", params={})


def test_interrupted_actions_yield_interrupted_run_status():
    assembler = ExecutionReportAssembler()

    status = assembler._determine_overall_status(
        [_log(ActionStatus.INTERRUPTED), _log(ActionStatus.SKIPPED)]
    )

    assert status == RunStatus.INTERRUPTED


def test_interrupted_takes_precedence_over_success():
    assembler = ExecutionReportAssembler()

    status = assembler._determine_overall_status(
        [_log(ActionStatus.SUCCESS), _log(ActionStatus.INTERRUPTED)]
    )

    assert status == RunStatus.INTERRUPTED


def test_failure_still_takes_precedence_over_interrupted():
    assembler = ExecutionReportAssembler()

    status = assembler._determine_overall_status(
        [_log(ActionStatus.FAILURE), _log(ActionStatus.INTERRUPTED)]
    )

    assert status == RunStatus.FAILURE
