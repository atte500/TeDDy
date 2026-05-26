from datetime import datetime
from typing import Optional, Sequence

from teddy_executor.core.domain.models import (
    ActionLog,
    ActionStatus,
    ExecutionReport,
    Plan,
    RunStatus,
    RunSummary,
)
from teddy_executor.core.ports.outbound.execution_report_assembler import (
    IExecutionReportAssembler,
)


class ExecutionReportAssembler(IExecutionReportAssembler):
    """
    Concrete implementation of the report assembly logic.
    """

    def assemble(
        self,
        plan: Plan,
        action_logs: Sequence[ActionLog],
        start_time: datetime,
        message: Optional[str] = None,
        is_session: bool = False,
        warnings: Optional[Sequence[str]] = None,
    ) -> ExecutionReport:
        """
        Calculates the final run status and constructs a complete ExecutionReport.
        """
        summary = RunSummary(
            status=self._determine_overall_status(action_logs),
            start_time=start_time,
            end_time=datetime.now(),
        )
        return ExecutionReport(
            run_summary=summary,
            plan_title=plan.title,
            rationale=plan.rationale,
            user_request=message or plan.metadata.get("user_request"),
            is_session=is_session or plan.is_session,
            metadata=plan.metadata,
            original_actions=plan.actions,
            action_logs=action_logs,
            warnings=warnings or [],
        )

    def _determine_overall_status(self, action_logs: Sequence[ActionLog]) -> RunStatus:
        """Determines the final run status based on the hierarchy of action outcomes."""
        if not action_logs:
            return RunStatus.SUCCESS

        statuses = [log.status for log in action_logs]
        if ActionStatus.FAILURE in statuses:
            return RunStatus.FAILURE

        # Success takes precedence: if any action succeeded, the run is a success.
        if ActionStatus.SUCCESS in statuses:
            return RunStatus.SUCCESS

        # If every single action was skipped, the run is skipped.
        if statuses and all(s == ActionStatus.SKIPPED for s in statuses):
            return RunStatus.SKIPPED

        return RunStatus.SUCCESS
