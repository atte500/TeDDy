from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING
import yaml
from teddy_executor.core.domain.models.execution_report import ExecutionReport

from typing import Sequence

if TYPE_CHECKING:
    from teddy_executor.core.domain.models.planning_ports import (
        SessionPorts,
    )
    from teddy_executor.core.domain.models.plan import Plan

    _ = SessionPorts

from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.session_manager import SessionState


class SessionLifecycleManager:
    """
    Manages the lifecycle of session turns, including finalization,
    resume state machine, and automated re-plan coordination.
    """

    def __init__(self, ports: "SessionPorts"):
        self._session_service = ports.session_service
        self._file_system_manager = ports.file_system_manager
        self._report_formatter = ports.report_formatter
        self._user_interactor = ports.user_interactor
        self._session_planner = ports.session_planner
        self._replanner = ports.replanner

    def resume(
        self,
        session_name: str,
        orchestrator: IRunPlanUseCase,
        interactive: bool = True,
        project_context: Optional[Any] = None,
    ) -> Optional[ExecutionReport]:
        """Implements the 'resume' state machine."""
        state, turn_path = self._session_service.get_session_state(session_name)

        if state == SessionState.PENDING_PLAN:
            plan_path = f"{turn_path}/plan.md"
            return orchestrator.execute(
                plan_path=plan_path,
                interactive=interactive,
                project_context=project_context,
            )

        if state == SessionState.EMPTY:
            return self._handle_planning_and_execution(
                turn_path,
                orchestrator,
                interactive,
                project_context=project_context,
            )

        if state == SessionState.COMPLETE_TURN:
            next_turn_dir = self._session_service.transition_to_next_turn(
                plan_path=f"{turn_path}/plan.md"
            )
            return self._handle_planning_and_execution(
                next_turn_dir,
                orchestrator,
                interactive,
                project_context=project_context,
            )

        return None

    def _handle_planning_and_execution(
        self,
        turn_dir: str,
        orchestrator: IRunPlanUseCase,
        interactive: bool,
        project_context: Optional[Any] = None,
    ) -> Optional[ExecutionReport]:
        """Triggers planning for a turn and then executes the resulting plan."""
        new_name = self._session_planner.trigger_new_plan(turn_dir)
        if not new_name or new_name == "CANCELLED":
            return None
        _, actual_turn_path = self._session_service.get_session_state(new_name)
        return orchestrator.execute(
            plan_path=f"{actual_turn_path}/plan.md",
            interactive=interactive,
            project_context=project_context,
        )

    def trigger_replan(  # noqa: PLR0913
        self,
        plan_path: str,
        errors: list[str],
        original_plan_content: str,
        title: str = "Unknown Plan",
        rationale: str = "Structural Error",
        failed_resources: Optional[dict[str, str]] = None,
        is_session: bool = False,
        validation_ast: Optional[str] = None,
        original_actions: Optional[Sequence[Any]] = None,
        plan: Optional["Plan"] = None,
    ) -> ExecutionReport:
        """Triggers the Automated Re-plan Loop."""
        self._user_interactor.display_message(
            "\n[yellow]Validation failed... replanning[/yellow]"
        )
        report = self._replanner.build_failure_report(
            errors,
            title,
            rationale,
            failed_resources or {},
            validation_ast=validation_ast,
            original_actions=original_actions,
            is_session=is_session,
        )
        next_turn_dir = self.finalize_turn(
            plan_path, report, is_validation_failure=True, plan=plan
        )

        self._replanner.trigger_replan_turn(
            next_turn_dir, errors, original_plan_content, validation_ast=validation_ast
        )
        return report

    def finalize_turn(
        self,
        plan_path: str,
        report: ExecutionReport,
        is_validation_failure: bool = False,
        plan: Optional[Any] = None,
    ) -> str:
        """Persists the report and transitions to the next turn."""
        turn_dir = Path(plan_path).parent
        meta_path = turn_dir / "meta.yaml"

        # Read current cost from meta.yaml
        turn_cost = 0.0
        if self._file_system_manager.path_exists(str(meta_path)):
            meta_content = self._file_system_manager.read_file(str(meta_path))
            meta_loaded = yaml.safe_load(str(meta_content))
            meta = meta_loaded if isinstance(meta_loaded, dict) else {}
            turn_cost = meta.get("turn_cost", 0.0)

        # 1. Persist the report to the current turn directory
        formatted_report = self._report_formatter.format(report)
        # Use root-relative path for report persistence to ensure context discovery
        report_file_path = self._session_service.to_root_relative(turn_dir, "report.md")
        self._file_system_manager.write_file(report_file_path, formatted_report)

        # Extract manual pruning paths from plan metadata
        pruned_paths = []
        if plan:
            raw_pruned = plan.metadata.get("pruned_context", "")
            if raw_pruned:
                pruned_paths = [p.strip() for p in raw_pruned.split(",") if p.strip()]

        # 2. Transition to next turn
        return self._session_service.transition_to_next_turn(
            plan_path=plan_path,
            execution_report=report,
            turn_cost=turn_cost,
            is_validation_failure=is_validation_failure,
            pruned_paths=pruned_paths,
        )
