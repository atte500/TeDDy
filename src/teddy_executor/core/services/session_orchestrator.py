from pathlib import Path
from typing import Any, Optional, cast

from teddy_executor.core.domain.models.execution_report import (
    ExecutionReport,
)
from teddy_executor.core.services.parser_reporting import (
    format_hybrid_ast_view,
)
from teddy_executor.core.domain.models.plan import Plan
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
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
        plan_validator,
        plan_parser,
        user_interactor,
        lifecycle_manager,
        replanner: SessionReplanner,
        context_service,
        config_service,
        llm_client,
        prompt_manager,
        pruning_service=None,
    ):
        self._execution_orchestrator = execution_orchestrator
        self._session_service = session_service
        self._file_system_manager = file_system_manager
        self._plan_validator = plan_validator
        self._plan_parser = plan_parser
        self._user_interactor = user_interactor
        self._lifecycle_manager = lifecycle_manager
        self._replanner = replanner
        self._context_service = context_service
        self._config_service = config_service
        self._llm_client = llm_client
        self._prompt_manager = prompt_manager
        self._pruning_service = pruning_service

    def resume(
        self,
        session_name: str,
        interactive: bool = True,
        project_context: Optional[Any] = None,
    ):
        """
        Implements the 'resume' state machine.
        """
        return self._lifecycle_manager.resume(
            session_name, self, interactive, project_context=project_context
        )

    def execute(  # noqa: PLR0913
        self,
        plan: Optional[Plan] = None,
        plan_content: Optional[str] = None,
        plan_path: Optional[str] = None,
        interactive: bool = True,
        message: Optional[str] = None,
        project_context: Optional[Any] = None,
    ) -> ExecutionReport:
        # 0. Detect Session Mode (requires plan_path and meta.yaml)
        is_session = self._is_session_mode(plan_path)

        # 1. Prepare Plan (Parse & Validate)
        result = self._prepare_plan(plan, plan_content, plan_path, is_session)
        if isinstance(result, ExecutionReport):
            return result
        plan = result

        # 3. Execution
        if is_session and plan_path and not project_context and interactive:
            context_files = self._session_service.resolve_context_paths(plan_path)
            # Use plan metadata as primary source for agent name, fallback to lifecycle manager
            agent_name = (
                plan.metadata.get("Agent")
                or plan.metadata.get("agent")
                or (
                    self._lifecycle_manager.get_agent_name(plan_path)
                    if hasattr(self._lifecycle_manager, "get_agent_name")
                    else "Unknown"
                )
            )
            total_window = self._llm_client.get_context_window()

            # R-10-12: Resolve system prompt and its token count
            system_prompt_tokens = 0
            # fetch_system_prompt requires turn_path; we derive it from plan_path
            turn_path = Path(plan_path).parent
            prompt_content = self._prompt_manager.fetch_system_prompt(
                agent_name.lower(), turn_path
            )
            if prompt_content:
                system_prompt_tokens = self._llm_client.get_text_token_count(
                    prompt_content
                )

            project_context = self._context_service.get_context(
                context_files=context_files,
                agent_name=agent_name,
                total_window=total_window,
            )
            # Update context with system info
            from dataclasses import is_dataclass, replace

            if is_dataclass(project_context):
                project_context = replace(
                    cast(Any, project_context),
                    agent_name=agent_name,
                    system_prompt_tokens=system_prompt_tokens,
                )
            if self._pruning_service:
                # R-10-12: Pass plan status to pruning service to trigger immediate recovery cleanup
                status = plan.metadata.get("Status") if plan else None
                project_context = self._pruning_service.prune(
                    project_context, current_status=status
                )

        report = self._execution_orchestrator.execute(
            plan=plan,
            plan_content=plan_content,
            plan_path=plan_path,
            interactive=interactive,
            message=message,
            project_context=project_context,
        )

        # 4. Turn Transition
        if is_session and plan_path:
            report = self._handle_aborted_session(report, plan)
            if report is None:
                import typer

                typer.secho("\nSession terminated.", fg=typer.colors.RED, err=True)
                return None  # type: ignore

            self._lifecycle_manager.finalize_turn(plan_path, report, plan=plan)

        return report

    def _handle_aborted_session(
        self, report: ExecutionReport, plan: Optional[Plan]
    ) -> ExecutionReport:
        """Handles user interaction and metadata updates when a session is aborted."""
        from dataclasses import replace
        from teddy_executor.core.domain.models import RunStatus

        if report.run_summary.status != RunStatus.ABORTED:
            return report

        import typer

        typer.secho("Plan aborted by user.", fg=typer.colors.YELLOW, err=True)

        # R-10-12: We always prompt for a NEW message when a plan is aborted,
        # unless one was explicitly captured during the abort process itself
        # (e.g. via the 'm' key in TUI). Pre-existing turn messages are ignored.
        new_message = self._user_interactor.ask_question(
            "Plan aborted. How do you want to proceed? (Empty response will quit session)"
        )

        # If still empty after potential prompt, return None to signal session termination.
        if not new_message:
            return None  # type: ignore

        # Update metadata (dict is mutable even in frozen dataclass)
        report.metadata["user_request"] = new_message
        # Replace report to include user_request so it shows in report.md header
        updated_report = replace(report, user_request=new_message)
        # Update plan metadata as well
        if plan:
            plan.metadata["user_request"] = new_message

        return updated_report

    def _prepare_plan(
        self,
        plan: Optional[Plan],
        plan_content: Optional[str],
        plan_path: Optional[str],
        is_session: bool,
    ) -> Plan | ExecutionReport:
        """Handles parsing and validation logic, potentially triggering a replan."""
        # Ensure plan object is marked if it was already resolved
        if plan:
            plan.is_session = is_session

        content = plan_content or (
            self._file_system_manager.read_file(plan_path) if plan_path else ""
        )
        if not plan:
            try:
                plan = self._plan_parser.parse(content, plan_path=plan_path)
            except Exception as e:
                if is_session and plan_path:
                    # R-10-12: Keep session loop alive by returning the re-plan report
                    return self._lifecycle_manager.trigger_replan(
                        plan_path=plan_path,
                        errors=[f"Structural error: {str(e)}"],
                        original_plan_content=content,
                    )
                raise

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

        return plan

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
            return self._plan_parser.parse(content, plan_path=plan_path)
        except Exception as e:
            if is_session and plan_path:
                # Ensure the rich diagnostic is visible to the user
                self._user_interactor.display_message(str(e))
                self._lifecycle_manager.trigger_replan(
                    plan_path=plan_path,
                    errors=[f"Structural error: {str(e)}"],
                    original_plan_content=content,
                )
                # Re-planning is already handled by trigger_replan
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
        error_messages = [e.message for e in errors]

        failed_resources = self._replanner.gather_failed_resources(errors)

        if is_session and plan_path:
            return self._lifecycle_manager.trigger_replan(
                plan_path=plan_path,
                errors=error_messages,
                original_plan_content=content,
                title=plan.title,
                rationale=plan.rationale,
                failed_resources=failed_resources,
                validation_ast=rich_ast,
                original_actions=plan.actions,
            )

        return self._replanner.build_failure_report(
            errors=error_messages,
            title=plan.title,
            rationale=plan.rationale,
            failed_resources=failed_resources,
            validation_ast=rich_ast,
            original_actions=plan.actions,
        )
