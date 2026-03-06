from pathlib import Path
from typing import Optional
from teddy_executor.core.domain.models.execution_report import ExecutionReport
from teddy_executor.core.domain.models.plan import Plan
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.file_system_manager import FileSystemManager
from teddy_executor.core.ports.outbound.markdown_report_formatter import (
    IMarkdownReportFormatter,
)


class SessionOrchestrator(IRunPlanUseCase):
    """
    A wrapper service implementing the 'Turn Transition Algorithm'
    around the base execution logic.
    """

    def __init__(
        self,
        execution_orchestrator,
        session_service,
        file_system_manager: FileSystemManager,
        report_formatter: IMarkdownReportFormatter,
    ):
        self._execution_orchestrator = execution_orchestrator
        self._session_service = session_service
        self._file_system_manager = file_system_manager
        self._report_formatter = report_formatter

    def execute(
        self,
        plan: Optional[Plan] = None,
        plan_content: Optional[str] = None,
        plan_path: Optional[str] = None,
        interactive: bool = True,
    ) -> ExecutionReport:
        # 1. Delegate core execution to the stateless orchestrator
        report = self._execution_orchestrator.execute(
            plan=plan,
            plan_content=plan_content,
            plan_path=plan_path,
            interactive=interactive,
        )

        # 2. Trigger stateful turn transition if a plan path is provided (Session Mode)
        if plan_path:
            # 2a. Persist the report to the current turn directory
            formatted_report = self._report_formatter.format(report)
            report_file_path = str(Path(plan_path).parent / "report.md")
            self._file_system_manager.write_file(report_file_path, formatted_report)

            # 2b. Transition to next turn
            self._session_service.transition_to_next_turn(
                plan_path=plan_path, execution_report=report
            )

        return report
