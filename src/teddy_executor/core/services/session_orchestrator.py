from pathlib import Path
from typing import Any, Optional

import yaml
from teddy_executor.core.domain.models.execution_report import (
    ExecutionReport,
)
from teddy_executor.core.services.parser_reporting import (
    assemble_logical_error_details,
    format_hybrid_ast_view,
)
from teddy_executor.core.domain.models.plan import Plan
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.markdown_report_formatter import (
    IMarkdownReportFormatter,
)
from teddy_executor.core.ports.outbound.session_manager import SessionState
from teddy_executor.core.services.session_planner import SessionPlanner
from teddy_executor.core.services.session_replanner import SessionReplanner


class SessionOrchestrator(IRunPlanUseCase):
    """
    A wrapper service implementing the 'Turn Transition Algorithm'
    around the base execution logic.
    """

    def __init__(  # noqa: PLR0913
        self,
        execution_orchestrator,
        session_service,
        file_system_manager: IFileSystemManager,
        report_formatter: IMarkdownReportFormatter,
        plan_validator,
        planning_service,
        plan_parser,
        user_interactor,
        replanner: SessionReplanner,
        session_planner: SessionPlanner,
    ):
        self._execution_orchestrator = execution_orchestrator
        self._session_service = session_service
        self._file_system_manager = file_system_manager
        self._report_formatter = report_formatter
        self._plan_validator = plan_validator
        self._planning_service = planning_service
        self._plan_parser = plan_parser
        self._user_interactor = user_interactor
        self._replanner = replanner
        self._session_planner = session_planner

    def resume(self, session_name: str, interactive: bool = True):
        """
        Implements the 'resume' state machine.
        """
        state, turn_path = self._session_service.get_session_state(session_name)

        if state == SessionState.PENDING_PLAN:
            plan_path = f"{turn_path}/plan.md"
            return self.execute(plan_path=plan_path, interactive=interactive)

        if state == SessionState.EMPTY:
            new_name = self._session_planner.trigger_new_plan(turn_path)
            if not new_name:
                return None
            # After planning, the turn is now PENDING_PLAN.
            # Resolve path again to account for potential renaming.
            _, actual_turn_path = self._session_service.get_session_state(new_name)
            return self.execute(
                plan_path=f"{actual_turn_path}/plan.md", interactive=interactive
            )

        if state == SessionState.COMPLETE_TURN:
            # Case C: Start next turn
            next_turn_dir = self._session_service.transition_to_next_turn(
                plan_path=f"{turn_path}/plan.md"
            )
            new_name = self._session_planner.trigger_new_plan(next_turn_dir)
            if not new_name:
                return None
            # After planning, the next turn is now PENDING_PLAN.
            _, actual_turn_path = self._session_service.get_session_state(new_name)
            return self.execute(
                plan_path=f"{actual_turn_path}/plan.md", interactive=interactive
            )

        return None

    def execute(
        self,
        plan: Optional[Plan] = None,
        plan_content: Optional[str] = None,
        plan_path: Optional[str] = None,
        interactive: bool = True,
    ) -> ExecutionReport:
        # 0. Detect Session Mode (requires plan_path and meta.yaml)
        is_session = self._is_session_mode(plan_path)

        # 1. Parsing
        content = plan_content or (
            self._file_system_manager.read_file(plan_path) if plan_path else ""
        )
        if not plan:
            plan = self._parse_and_handle_structural_errors(
                content, plan_path, is_session
            )

        # 2. Validation
        context_paths = (
            self._session_service.resolve_context_paths(plan_path)
            if is_session
            else None
        )
        errors = self._plan_validator.validate(plan, context_paths=context_paths)
        if errors:
            return self._handle_logical_validation_errors(
                plan, errors, content, plan_path, is_session
            )

        # 3. Execution
        report = self._execution_orchestrator.execute(
            plan=plan,
            plan_content=plan_content,
            plan_path=plan_path,
            interactive=interactive,
        )

        # 4. Turn Transition
        if is_session and plan_path:
            self._finalize_turn(plan_path, report)

        return report

    def _is_session_mode(self, plan_path: Optional[str]) -> bool:
        """Determines if the orchestrator should operate in Session Mode."""
        if not plan_path:
            return False
        meta_path = Path(plan_path).parent / "meta.yaml"
        return self._file_system_manager.path_exists(str(meta_path))

    def _parse_and_handle_structural_errors(
        self, content: str, plan_path: Optional[str], is_session: bool
    ) -> Plan:
        """Parses the plan and triggers a replan on structural failure."""
        try:
            return self._plan_parser.parse(content)
        except Exception as e:
            if is_session and plan_path:
                # Ensure the rich diagnostic is visible to the user
                self._user_interactor.display_message(str(e))
                self._trigger_replan(
                    plan_path=plan_path,
                    errors=[f"Structural error: {str(e)}"],
                    original_plan_content=content,
                )
                raise RuntimeError(
                    "Structural validation failed. Re-plan triggered."
                ) from e
            raise

    def _handle_logical_validation_errors(  # noqa: PLR0913
        self,
        plan: Plan,
        errors: list[Any],
        content: str,
        plan_path: Optional[str],
        is_session: bool,
    ) -> ExecutionReport:
        """Formats logical errors and handles the failure report/replan."""
        rich_ast = (
            format_hybrid_ast_view(plan.source_doc, errors) if plan.source_doc else ""
        )
        error_msg = assemble_logical_error_details(plan, errors)
        full_error_msg = error_msg + rich_ast

        failed_resources = self._replanner.gather_failed_resources(errors)

        if is_session and plan_path:
            return self._trigger_replan(
                plan_path=plan_path,
                errors=[full_error_msg],
                original_plan_content=content,
                title=plan.title,
                rationale=plan.rationale,
                failed_resources=failed_resources,
            )

        return self._replanner.build_failure_report(
            errors=[full_error_msg],
            title=plan.title,
            rationale=plan.rationale,
            failed_resources=failed_resources,
        )

    def _finalize_turn(
        self,
        plan_path: str,
        report: ExecutionReport,
        is_validation_failure: bool = False,
    ):
        """Persists the report and transitions to the next turn."""
        turn_dir = Path(plan_path).parent
        meta_path = turn_dir / "meta.yaml"

        # Read current cost from meta.yaml
        turn_cost = 0.0
        if self._file_system_manager.path_exists(str(meta_path)):
            meta_content = self._file_system_manager.read_file(str(meta_path))
            # Defensive: cast content to str to prevent yaml.safe_load hanging on MagicMocks
            meta_loaded = yaml.safe_load(str(meta_content))
            meta = meta_loaded if isinstance(meta_loaded, dict) else {}
            turn_cost = meta.get("turn_cost", 0.0)

        # 1. Persist the report to the current turn directory
        formatted_report = self._report_formatter.format(report)
        report_file_path = str(turn_dir / "report.md")
        self._file_system_manager.write_file(report_file_path, formatted_report)

        # 2. Transition to next turn
        return self._session_service.transition_to_next_turn(
            plan_path=plan_path,
            execution_report=report,
            is_validation_failure=is_validation_failure,
            turn_cost=turn_cost,
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
        report = self._replanner.build_failure_report(
            errors, title, rationale, failed_resources or {}
        )
        next_turn_dir = self._finalize_turn(
            plan_path, report, is_validation_failure=True
        )
        self._replanner.trigger_replan_turn(
            next_turn_dir, errors, original_plan_content
        )
        return report
