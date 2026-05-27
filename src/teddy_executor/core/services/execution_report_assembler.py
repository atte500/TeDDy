from datetime import datetime
from typing import Sequence

from teddy_executor.core.domain.models import (
    ActionLog,
    ActionStatus,
    ExecutionReport,
    ReportAssemblyData,
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
        data: ReportAssemblyData,
    ) -> ExecutionReport:
        """
        Calculates the final run status and constructs a complete ExecutionReport.
        """
        summary = RunSummary(
            status=self._determine_overall_status(data.action_logs),
            start_time=data.start_time,
            end_time=datetime.now(),
        )
        return ExecutionReport(
            run_summary=summary,
            plan_title=data.plan.title,
            rationale=data.plan.rationale,
            user_request=data.message or data.plan.metadata.get("user_request"),
            is_session=data.is_session or data.plan.is_session,
            metadata=data.plan.metadata,
            original_actions=data.plan.actions,
            action_logs=data.action_logs,
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
