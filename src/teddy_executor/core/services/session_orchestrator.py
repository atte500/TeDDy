from pathlib import Path
from typing import Any, Optional, cast

import anyio
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
    ):
        self._execution_orchestrator = execution_orchestrator
        self._session_service = session_service
        self._file_system_manager = file_system_manager
        self._plan_validator = plan_validator
        self._plan_parser = plan_parser
        self._user_interactor = user_interactor
        self._lifecycle_manager = lifecycle_manager
        self._replanner = replanner

    async def async_execute(
        self,
        plan: Optional[Plan] = None,
        plan_content: Optional[str] = None,
        plan_path: Optional[str] = None,
        interactive: bool = True,
        message: Optional[str] = None,
    ) -> ExecutionReport:
        """
        Asynchronously executes a plan and returns a report.
        """
        # 0. Detect Session Mode
        is_session = await anyio.to_thread.run_sync(self._is_session_mode, plan_path)

        # 1. Parsing
        if not plan:
            # Ensure content is always a string to satisfy subsequent calls
            fetched_content = ""
            if plan_path:
                fetched_content = await anyio.to_thread.run_sync(
                    self._file_system_manager.read_file, plan_path
                )

            content: str = plan_content if plan_content is not None else fetched_content
            # Cast or hint plan as non-Optional Plan for logical validation
            plan = cast(
                Plan,
                await anyio.to_thread.run_sync(
                    self._parse_and_handle_structural_errors,
                    content,
                    plan_path,
                    is_session,
                ),
            )

        # 2. Validation
        context_paths = None
        if is_session:
            context_paths = await self._session_service.async_resolve_context_paths(
                plan_path
            )

        errors = await anyio.to_thread.run_sync(
            self._plan_validator.validate, plan, context_paths
        )
        if errors:
            return await self.async_handle_logical_validation_errors(
                plan,
                errors,
                getattr(plan, "raw_content", "") or "",
                plan_path,
                is_session,
            )

        # 3. Execution
        report = await self._execution_orchestrator.async_execute(
            plan=plan,
            plan_content=plan_content,
            plan_path=plan_path,
            interactive=interactive,
            message=message,
        )

        # 4. Turn Transition
        if is_session and plan_path:
            await self._lifecycle_manager.async_finalize_turn(plan_path, report)

        return report

    async def async_resume(
        self,
        session_name: str,
        interactive: bool = True,
        message: Optional[str] = None,
    ) -> Optional[ExecutionReport]:
        """
        Asynchronously resumes the session based on its state.
        """
        return await self._lifecycle_manager.async_resume(
            session_name, self, interactive, message
        )

    def resume(
        self,
        session_name: str,
        interactive: bool = True,
        message: Optional[str] = None,
    ):
        """
        Implements the 'resume' state machine.
        """
        return self._lifecycle_manager.resume(session_name, self, interactive, message)

    def execute(
        self,
        plan: Optional[Plan] = None,
        plan_content: Optional[str] = None,
        plan_path: Optional[str] = None,
        interactive: bool = True,
        message: Optional[str] = None,
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
            message=message,
        )

        # 4. Turn Transition
        if is_session and plan_path:
            self._lifecycle_manager.finalize_turn(plan_path, report)

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
                raise RuntimeError(
                    "Structural validation failed. Re-plan triggered."
                ) from e
            raise

    async def async_handle_logical_validation_errors(  # noqa: PLR0913
        self,
        plan: Plan,
        errors: list[Any],
        content: str,
        plan_path: Optional[str],
        is_session: bool,
    ) -> ExecutionReport:
        """Asynchronously formats logical errors and handles the failure report/replan."""
        rich_ast = (
            format_hybrid_ast_view(plan.source_doc, errors) if plan.source_doc else ""
        )
        error_messages = [e.message for e in errors]

        failed_resources = await self._replanner.async_gather_failed_resources(errors)

        if is_session and plan_path:
            return await self._lifecycle_manager.async_trigger_replan(
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
