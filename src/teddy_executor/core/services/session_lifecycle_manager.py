from pathlib import Path
from typing import Any, Optional
import yaml
import anyio
from teddy_executor.core.domain.models.execution_report import ExecutionReport

from typing import Sequence

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
        message: Optional[str] = None,
    ) -> Optional[ExecutionReport]:
        """Implements the 'resume' state machine."""
        state, turn_path = self._session_service.get_session_state(session_name)

        if state == SessionState.PENDING_PLAN:
            plan_path = f"{turn_path}/plan.md"
            return orchestrator.execute(
                plan_path=plan_path, interactive=interactive, message=message
            )

        if state == SessionState.EMPTY:
            return self._handle_planning_and_execution(
                turn_path, orchestrator, interactive, message=message
            )

        if state == SessionState.COMPLETE_TURN:
            next_turn_dir = self._session_service.transition_to_next_turn(
                plan_path=f"{turn_path}/plan.md"
            )
            return self._handle_planning_and_execution(
                next_turn_dir, orchestrator, interactive, message=message
            )

        return None

    async def async_resume(
        self,
        session_name: str,
        orchestrator: IRunPlanUseCase,
        interactive: bool = True,
        message: Optional[str] = None,
    ) -> Optional[ExecutionReport]:
        """Asynchronously resumes the session based on its state."""
        state, turn_path = await self._session_service.async_get_session_state(
            session_name
        )

        if state == SessionState.PENDING_PLAN:
            plan_path = f"{turn_path}/plan.md"
            return await orchestrator.async_execute(
                plan_path=plan_path, interactive=interactive, message=message
            )

        if state == SessionState.EMPTY:
            return await self._async_handle_planning_and_execution(
                turn_path, orchestrator, interactive, message=message
            )

        if state == SessionState.COMPLETE_TURN:
            next_turn_dir = await self._session_service.async_transition_to_next_turn(
                plan_path=f"{turn_path}/plan.md",
            )
            return await self._async_handle_planning_and_execution(
                next_turn_dir, orchestrator, interactive, message=message
            )

        return None

    def _handle_planning_and_execution(
        self,
        turn_dir: str,
        orchestrator: IRunPlanUseCase,
        interactive: bool,
        message: Optional[str] = None,
    ) -> Optional[ExecutionReport]:
        """Triggers planning for a turn and then executes the resulting plan."""
        new_name = self._session_planner.trigger_new_plan(turn_dir, message=message)
        if not new_name or new_name == "CANCELLED":
            return None
        _, actual_turn_path = self._session_service.get_session_state(new_name)
        return orchestrator.execute(
            plan_path=f"{actual_turn_path}/plan.md",
            interactive=interactive,
            message=message,
        )

    async def _async_handle_planning_and_execution(
        self,
        turn_dir: str,
        orchestrator: IRunPlanUseCase,
        interactive: bool,
        message: Optional[str] = None,
    ) -> Optional[ExecutionReport]:
        """Asynchronously triggers planning and execution."""
        new_name = await self._session_planner.async_trigger_new_plan(
            turn_dir, message=message
        )
        if not new_name or new_name == "CANCELLED":
            return None

        _, actual_turn_path = await self._session_service.async_get_session_state(
            new_name
        )
        return await orchestrator.async_execute(
            plan_path=f"{actual_turn_path}/plan.md",
            interactive=interactive,
            message=message,
        )

    def trigger_replan(  # noqa: PLR0913
        self,
        plan_path: str,
        errors: list[str],
        original_plan_content: str,
        title: str = "Unknown Plan",
        rationale: str = "Structural Error",
        failed_resources: Optional[dict[str, str]] = None,
        validation_ast: Optional[str] = None,
        original_actions: Optional[Sequence[Any]] = None,
    ) -> ExecutionReport:
        """Triggers the Automated Re-plan Loop."""
        report = self._replanner.build_failure_report(
            errors,
            title,
            rationale,
            failed_resources or {},
            validation_ast=validation_ast,
            original_actions=original_actions,
        )
        next_turn_dir = self.finalize_turn(
            plan_path, report, is_validation_failure=True
        )

        self.display_planning_progress(next_turn_dir)
        self._replanner.trigger_replan_turn(
            next_turn_dir, errors, original_plan_content, validation_ast=validation_ast
        )
        return report

    async def async_trigger_replan(  # noqa: PLR0913
        self,
        plan_path: str,
        errors: list[str],
        original_plan_content: str,
        title: str = "Unknown Plan",
        rationale: str = "Structural Error",
        failed_resources: Optional[dict[str, str]] = None,
        validation_ast: Optional[str] = None,
        original_actions: Optional[Sequence[Any]] = None,
    ) -> ExecutionReport:
        """Asynchronously triggers the Automated Re-plan Loop."""
        report = self._replanner.build_failure_report(
            errors,
            title,
            rationale,
            failed_resources or {},
            validation_ast=validation_ast,
            original_actions=original_actions,
        )
        next_turn_dir = await self.async_finalize_turn(
            plan_path, report, is_validation_failure=True
        )

        await self.async_display_planning_progress(next_turn_dir)
        await self._replanner.async_trigger_replan_turn(
            next_turn_dir, errors, original_plan_content, validation_ast=validation_ast
        )
        return report

    def finalize_turn(
        self,
        plan_path: str,
        report: ExecutionReport,
        is_validation_failure: bool = False,
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
        report_file_path = str(turn_dir / "report.md")
        self._file_system_manager.write_file(report_file_path, formatted_report)

        # 2. Transition to next turn
        return self._session_service.transition_to_next_turn(
            plan_path=plan_path,
            execution_report=report,
            turn_cost=turn_cost,
            is_validation_failure=is_validation_failure,
        )

    async def async_finalize_turn(
        self,
        plan_path: str,
        report: ExecutionReport,
        is_validation_failure: bool = False,
    ) -> str:
        """Asynchronously persists the report and transitions to the next turn."""
        return await anyio.to_thread.run_sync(
            self.finalize_turn, plan_path, report, is_validation_failure
        )

    def display_planning_progress(self, turn_dir: Any) -> None:
        """Displays a progress message before planning starts."""
        turn_dir_str = str(turn_dir)
        turn_id = Path(turn_dir_str).name
        meta_path = Path(turn_dir_str) / "meta.yaml"

        agent_name = "pathfinder"
        if self._file_system_manager.path_exists(str(meta_path)):
            content = self._file_system_manager.read_file(str(meta_path))
            meta = yaml.safe_load(str(content)) or {}
            if isinstance(meta, dict):
                agent_name = meta.get("agent_name", agent_name)

        msg = f"[cyan][{turn_id}] Planning Turn with {agent_name}...[/cyan]"
        self._user_interactor.display_message(msg)

    async def async_display_planning_progress(self, turn_dir: Any) -> None:
        """Asynchronously displays a progress message."""
        await anyio.to_thread.run_sync(self.display_planning_progress, turn_dir)
