import logging
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
from teddy_executor.core.utils.io import Tee as _Tee
import typer

logger = logging.getLogger(__name__)


def _extract_status_emoji(raw_status: str) -> str:
    """Extract the first status emoji (🟢, 🟡, 🔴) from a status string."""
    for emoji in ("🟢", "🟡", "🔴"):
        if emoji in raw_status:
            return emoji
    return ""


def _print_initial_request(message: Optional[str], is_session: bool) -> None:
    """Print the initial user request before the turn header.

    Only prints when is_session=True and message is non-empty.
    Output::
        Initial Request:
        {content}
        (blank line separator)
    """
    if not is_session or not message or not message.strip():
        return
    typer.secho("Initial Request:")
    typer.secho(message.strip())
    typer.secho("")


def _print_header_bar(plan: Any, is_session: bool) -> None:
    """Print the plan status emoji and title after telemetry, before actions.

    Only prints when is_session=True.
    Output: {emoji} {title}  (no blank lines around it)
    """
    if not is_session:
        return
    raw_status = (
        (plan.metadata or {}).get("Status") or (plan.metadata or {}).get("status") or ""
    )
    emoji = _extract_status_emoji(raw_status)
    title = plan.title or ""
    parts = [p for p in [emoji, title] if p]
    if parts:
        typer.secho(" ".join(parts))


def _print_user_message(message: Optional[str], is_session: bool) -> None:
    """Print the user message after all actions execute.

    Only prints when is_session=True and message is non-empty.
    Output::
        (blank line)
        User Message:
        {content}
        (trailing newline)
    """
    if not is_session or not message or not message.strip():
        return
    typer.secho("")
    typer.secho("User Message:")
    typer.secho(message.strip())
    typer.secho("")


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
            session_name,
            self,
            interactive,
            project_context=project_context,
        )

    def execute(  # noqa: PLR0913, C901
        self,
        plan: Optional[Plan] = None,
        plan_content: Optional[str] = None,
        plan_path: Optional[str] = None,
        interactive: bool = True,
        message: Optional[str] = None,
        project_context: Optional[Any] = None,
    ) -> ExecutionReport:
        # Empty message signals session termination (no report.md created).
        if message is not None and not message.strip():
            return None  # type: ignore

        # 0. Detect Session Mode (requires plan_path and meta.yaml)
        is_session = self._is_session_mode(plan_path)

        # Print initial request before the turn header (only for session with non-empty message)
        if is_session and message and message.strip():
            _print_initial_request(message, is_session)

        # Install Tee for history.log capture (guarded: skip if lifecycle manager already installed)
        _tee = None
        if is_session and plan_path and not self._lifecycle_manager.tee_active:
            try:
                _log_path = Path(plan_path).parent.parent / "history.log"
                # Defensive guard: ensure history.log is never written to project root.
                # If resolved path equals project root or CWD, redirect to .tmp/.
                _resolved = str(_log_path.resolve())
                _project_root = str(Path.cwd().resolve())
                if _resolved.rstrip("/") == _project_root.rstrip("/"):
                    _safe_dir = Path(plan_path).parent.parent / ".tmp"
                    _safe_dir.mkdir(parents=True, exist_ok=True)
                    _log_path = _safe_dir / "history.log"
                _tee = _Tee(_log_path)
                _tee.__enter__()
            except Exception:
                _tee = None

        try:
            # 1. Resolve Plan (Parse only)
            result = self._prepare_plan_parsing(
                plan, plan_content, plan_path, is_session
            )
            if isinstance(result, ExecutionReport):
                return result
            plan = result

            # 2. Context Preparation (Gather, Prune, Harvest)
            # We must harvest context BEFORE validation so that pruned paths persist across replans
            if is_session and plan_path and not project_context:
                context_files = self._session_service.resolve_context_paths(plan_path)
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

                cache_dir = str(Path(plan_path).parent.parent)
                project_context = self._context_service.get_context(
                    context_files=context_files,
                    agent_name=agent_name,
                    total_window=total_window,
                    cache_dir=cache_dir,
                )
                from dataclasses import is_dataclass, replace

                if is_dataclass(project_context):
                    # Compute system prompt tokens for context display (same pattern as planning_service.py)
                    system_prompt = self._prompt_manager.fetch_system_prompt(
                        agent_name, Path(plan_path).parent
                    )
                    model = str(
                        self._config_service.get_setting("llm.model") or ""
                    )
                    try:
                        system_token_count = self._llm_client.get_text_token_count(
                            system_prompt, model=model
                        )
                    except Exception:
                        system_token_count = 0
                    project_context = replace(
                        cast(Any, project_context),
                        agent_name=agent_name,
                        system_prompt_tokens=system_token_count,
                    )
                if self._pruning_service:
                    status = plan.metadata.get("Status") if plan else None
                    project_context = self._pruning_service.prune(
                        project_context, current_status=status
                    )

            self._harvest_context(
                is_session=is_session,
                project_context=project_context,
                plan=plan,
            )

            # 3. Validation (passing refined context)
            result = self._validate_plan_with_context(
                plan, plan_path, is_session, project_context
            )
            if isinstance(result, ExecutionReport):
                return result

            # Print header bar (emoji + title) before execution logs (only for session mode)
            if is_session:
                _print_header_bar(plan, is_session)

            # 4. Execution
            report = self._execution_orchestrator.execute(
                plan=plan,
                plan_content=plan_content,
                plan_path=plan_path,
                interactive=interactive,
                message=message,
                project_context=project_context,
            )

            # 4a. Empty user reply after communication turn → terminate session immediately (no report.md)
            if report and plan.is_communication_turn():
                user_reply = next(
                    (
                        log.details
                        for log in report.action_logs
                        if log.action_type == "MESSAGE"
                    ),
                    None,
                )
                if user_reply is not None and not user_reply.strip():
                    import typer

                    typer.secho("\nSession terminated.", fg=typer.colors.RED, err=True)
                    typer.secho(
                        "To continue the session, use `teddy resume [session_path]`.",
                        err=True,
                    )
                    return None  # type: ignore

            # Print user message after all actions executed (only for session with non-empty message)
            if is_session and message and message.strip():
                _print_user_message(message, is_session)

            # 4. Turn Transition
            if is_session and plan_path:
                report = self._handle_aborted_session(report, plan)
                if report is None:
                    import typer

                    typer.secho("\nSession terminated.", fg=typer.colors.RED, err=True)
                    typer.secho(
                        "To continue the session, use `teddy resume [session_path]`.",
                        err=True,
                    )
                    return None  # type: ignore

                self._lifecycle_manager.finalize_turn(plan_path, report, plan=plan)

            return report

        finally:
            if _tee is not None:
                try:
                    _tee.__exit__(None, None, None)
                except Exception:
                    logger.exception("Failed to clean up Tee during session execute")

    def _harvest_context(
        self,
        is_session: bool,
        project_context: Optional[Any],
        plan: Plan,
    ) -> None:
        """Harvests unselected context paths."""
        if is_session and project_context:
            if hasattr(project_context, "items") and project_context.items:
                pruned_paths = [
                    item.path for item in project_context.items if not item.selected
                ]
                if pruned_paths:
                    plan.metadata["pruned_context"] = ",".join(pruned_paths)
                else:
                    plan.metadata.pop("pruned_context", None)

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

        # We always prompt for a NEW message when a plan is aborted,
        # unless one was explicitly captured during the abort process itself
        # (e.g. via the 'm' key in TUI). Pre-existing turn messages are ignored.
        new_message = self._user_interactor.ask_question(
            "Plan aborted. How do you want to proceed?"
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

    def _prepare_plan_parsing(
        self,
        plan: Optional[Plan],
        plan_content: Optional[str],
        plan_path: Optional[str],
        is_session: bool,
    ) -> Plan | ExecutionReport:
        """Handles parsing only, potentially triggering a replan on structural error."""
        if plan:
            plan.is_session = is_session

        # Defensive check for missing plan file
        if plan_path and not plan_content:
            if not self._file_system_manager.path_exists(plan_path):
                error_msg = f"Plan file not found: {plan_path}"
                if is_session:
                    return self._lifecycle_manager.trigger_replan(
                        plan_path=plan_path,
                        errors=[error_msg],
                        original_plan_content="",
                    )
                return self._replanner.build_failure_report(
                    errors=[error_msg],
                    title="Missing Plan",
                    rationale="The plan file could not be found on disk.",
                    failed_resources={},
                )

        content = plan_content or (
            self._file_system_manager.read_file(plan_path) if plan_path else ""
        )
        if not plan:
            try:
                plan = self._plan_parser.parse(content, plan_path=plan_path)
            except Exception as e:
                if is_session and plan_path:
                    return self._lifecycle_manager.trigger_replan(
                        plan_path=plan_path,
                        errors=[f"Structural error: {str(e)}"],
                        original_plan_content=content,
                    )
                raise
        return plan

    def _validate_plan_with_context(
        self,
        plan: Plan,
        plan_path: Optional[str],
        is_session: bool,
        project_context: Optional[Any],
    ) -> Plan | ExecutionReport:
        """Handles logical validation with optional refined context."""
        context_paths = None
        if is_session and plan_path:
            # Prefer active project context (respecting pruning) if available
            if project_context and hasattr(project_context, "items"):
                context_paths = {
                    "Session": [],  # Pruning logic already applied
                    "Turn": [
                        item.path for item in project_context.items if item.selected
                    ],
                }
            else:
                context_paths = self._session_service.resolve_context_paths(plan_path)

        errors = self._plan_validator.validate(plan, context_paths=context_paths)
        if errors:
            content = (
                self._file_system_manager.read_file(plan_path) if plan_path else ""
            )
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

        failed_resources = self._replanner.gather_failed_resources(
            errors, is_session=is_session
        )

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
                plan=plan,
                is_session=is_session,
            )

        return self._replanner.build_failure_report(
            errors=error_messages,
            title=plan.title,
            rationale=plan.rationale,
            failed_resources=failed_resources,
            validation_ast=rich_ast,
            original_actions=plan.actions,
        )
