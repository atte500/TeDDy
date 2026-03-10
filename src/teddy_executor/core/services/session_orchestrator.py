from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from teddy_executor.core.domain.models.execution_report import (
    ExecutionReport,
    RunStatus,
    RunSummary,
)
from teddy_executor.core.domain.models.plan import Plan
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.file_system_manager import FileSystemManager
from teddy_executor.core.ports.outbound.markdown_report_formatter import (
    IMarkdownReportFormatter,
)
from teddy_executor.core.ports.outbound.session_manager import SessionState


class SessionOrchestrator(IRunPlanUseCase):
    """
    A wrapper service implementing the 'Turn Transition Algorithm'
    around the base execution logic.
    """

    def __init__(  # noqa: PLR0913
        self,
        execution_orchestrator,
        session_service,
        file_system_manager: FileSystemManager,
        report_formatter: IMarkdownReportFormatter,
        plan_validator,
        planning_service,
        plan_parser,
        user_interactor,
    ):
        self._execution_orchestrator = execution_orchestrator
        self._session_service = session_service
        self._file_system_manager = file_system_manager
        self._report_formatter = report_formatter
        self._plan_validator = plan_validator
        self._planning_service = planning_service
        self._plan_parser = plan_parser
        self._user_interactor = user_interactor

    def resume(self, session_name: str, interactive: bool = True):
        """
        Implements the 'resume' state machine.
        """
        state, turn_path = self._session_service.get_session_state(session_name)

        if state == SessionState.PENDING_PLAN:
            plan_path = f"{turn_path}/plan.md"
            return self.execute(plan_path=plan_path, interactive=interactive)

        if state == SessionState.EMPTY:
            return self._trigger_new_plan(turn_path)

        if state == SessionState.COMPLETE_TURN:
            # Case C: Start next turn
            next_turn_dir = self._session_service.transition_to_next_turn(
                plan_path=f"{turn_path}/plan.md"
            )
            return self._trigger_new_plan(next_turn_dir)

        return None

    def _trigger_new_plan(self, turn_dir: str):
        """Prompts user and triggers planning."""
        message = self._user_interactor.prompt("Enter your instructions for the AI")
        if not message:
            return None

        # Add helpful hint for alignment
        hint = "\n\n*(Stop to reply to this user request and ensure alignment before proceeding)*"
        message += hint

        # Resolve context files
        # PlanningService expects context_files dict if available
        context_files = None
        turn_p = Path(turn_dir)
        turn_context = turn_p / "turn.context"
        session_context = turn_p.parent / "session.context"
        meta_yaml = turn_p / "meta.yaml"

        if (
            self._file_system_manager.path_exists(str(turn_context))
            and self._file_system_manager.path_exists(str(session_context))
            and self._file_system_manager.path_exists(str(meta_yaml))
        ):
            context_files = {
                "Turn": [str(turn_context)],
                "Session": [str(session_context)],
            }

        self._planning_service.generate_plan(
            user_message=message, turn_dir=turn_dir, context_files=context_files
        )
        return None

    def execute(
        self,
        plan: Optional[Plan] = None,
        plan_content: Optional[str] = None,
        plan_path: Optional[str] = None,
        interactive: bool = True,
    ) -> ExecutionReport:
        # 0. Parsing and Validation Gate
        content = plan_content
        if not content and plan_path:
            content = self._file_system_manager.read_file(plan_path)

        if not plan:
            try:
                plan = self._plan_parser.parse(content)
            except Exception as e:
                if plan_path:
                    return self._trigger_replan(
                        plan_path=plan_path,
                        errors=[f"Structural error: {str(e)}"],
                        original_plan_content=content or "",
                    )
                raise

        # Resolve context and validate
        context_paths = (
            self._session_service.resolve_context_paths(plan_path)
            if plan_path
            else None
        )
        errors = self._plan_validator.validate(plan, context_paths=context_paths)

        if errors:
            failed_resources = self._gather_failed_resources(errors)
            if plan_path:
                return self._trigger_replan(
                    plan_path=plan_path,
                    errors=[e.message for e in errors],
                    original_plan_content=content or "",
                    title=plan.title,
                    rationale=plan.rationale,
                    failed_resources=failed_resources,
                )
            # Manual Mode Validation Failure
            now = datetime.now(timezone.utc)
            return ExecutionReport(
                run_summary=RunSummary(
                    status=RunStatus.VALIDATION_FAILED,
                    start_time=now,
                    end_time=now,
                    error="Plan validation failed.",
                ),
                plan_title=plan.title,
                rationale=plan.rationale,
                action_logs=[],
                validation_result=[e.message for e in errors],
                failed_resources=failed_resources,
            )

        # 1. Delegate core execution to the stateless orchestrator
        report = self._execution_orchestrator.execute(
            plan=plan,
            plan_content=plan_content,
            plan_path=plan_path,
            interactive=interactive,
        )

        # 2. Trigger stateful turn transition if a plan path is provided (Session Mode)
        if plan_path:
            self._finalize_turn(plan_path, report)

        return report

    def _finalize_turn(
        self,
        plan_path: str,
        report: ExecutionReport,
        is_validation_failure: bool = False,
    ):
        """Persists the report and transitions to the next turn."""
        # 1. Persist the report to the current turn directory
        formatted_report = self._report_formatter.format(report)
        report_file_path = str(Path(plan_path).parent / "report.md")
        self._file_system_manager.write_file(report_file_path, formatted_report)

        # 2. Transition to next turn
        return self._session_service.transition_to_next_turn(
            plan_path=plan_path,
            execution_report=report,
            is_validation_failure=is_validation_failure,
        )

    def _trigger_replan(  # noqa: PLR0913
        self,
        plan_path: str,
        errors: list[str],
        original_plan_content: str,
        title: str = "Unknown Plan",
        rationale: str = "Structural Error",
        failed_resources: Optional[dict[str, str]] = None,
    ) -> ExecutionReport:
        """Triggers the Automated Re-plan Loop."""
        # a. Create Validation Failure Report
        now = datetime.now(timezone.utc)
        summary = RunSummary(
            status=RunStatus.VALIDATION_FAILED,
            start_time=now,
            end_time=now,
            error="Plan validation failed.",
        )
        report = ExecutionReport(
            run_summary=summary,
            plan_title=title,
            rationale=rationale,
            action_logs=[],  # No actions executed
            validation_result=errors,
            failed_resources=failed_resources,
        )

        # b. Persist and Transition
        next_turn_dir = self._finalize_turn(
            plan_path, report, is_validation_failure=True
        )

        # c. Trigger re-plan
        error_messages = [f"- {e}" for e in errors]
        feedback = (
            "The previous plan failed validation. Please review the errors and the original plan, then generate a corrected version.\n\n"
            "## Validation Errors:\n" + "\n".join(error_messages) + "\n\n"
            f"## Original Faulty Plan:\n"
            f"````````````markdown\n{original_plan_content}\n````````````"
        )
        self._planning_service.generate_plan(
            user_message=feedback, turn_dir=next_turn_dir
        )

        return report

    def _gather_failed_resources(self, errors: list) -> dict[str, str]:
        """Collects the contents of files that caused validation errors."""
        resources = {}
        for error in errors:
            path = getattr(error, "file_path", None)
            if path:
                try:
                    # Normalize path for FileSystemManager
                    clean_path = path.lstrip("/")
                    if self._file_system_manager.path_exists(clean_path):
                        resources[path] = self._file_system_manager.read_file(
                            clean_path
                        )
                except Exception:  # nosec B110
                    pass
        return resources
