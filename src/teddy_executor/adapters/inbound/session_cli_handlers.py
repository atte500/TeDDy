from pathlib import Path
from typing import Dict, Optional, Sequence
import typer
from punq import Container

from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.inbound.init import IInitUseCase
from teddy_executor.core.ports.inbound.planning_use_case import IPlanningUseCase
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.domain.models.session import SessionOptions
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.ports.outbound.session_loop_guard import ISessionLoopGuard
from teddy_executor.core.utils.string import slugify
from teddy_executor.adapters.inbound.cli_formatter import format_project_context
from teddy_executor.adapters.inbound.cli_helpers import (
    echo_and_copy,
)


def _determine_session_name(name: Optional[str], message: Optional[str]) -> str:
    """Determine session name (slugify message if name is missing)."""
    if name:
        return name
    if message:
        return slugify(message)
    return "session-auto"


def handle_new_session(  # noqa: PLR0913
    container: Container,
    name: Optional[str],
    agent: str,
    interactive: bool = True,
    no_copy: bool = False,
    message: Optional[str] = None,
    additional_context: Optional[list[str]] = None,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
):
    """Logic for the 'start' command."""
    from teddy_executor.adapters.inbound.cli_helpers import handle_report_output

    try:
        # 0. Ensure project is initialized
        container.resolve(IInitUseCase).ensure_initialized()

        # 1. Pre-flight checks (Fail-fast before user interaction)
        typer.echo("Checking configurations...", err=True)
        _run_cli_preflight_check(container, agent=agent)
        _echo_config_success(container, agent)

        session_manager: ISessionManager = container.resolve(ISessionManager)
        user_interactor: IUserInteractor = container.resolve(IUserInteractor)

        # 2. Resolve message first if missing
        if message is None:
            message = user_interactor.ask_question("What are we working on?")
            if not message:
                raise EOFError("No terminal input provided for initial message.")

        # 2. Determine session name (slugify message if name is missing)
        actual_name = _determine_session_name(name, message)
        options = SessionOptions(
            name=actual_name,
            agent_name=agent,
            initial_request=message,
            additional_context=additional_context or [],
            model=model,
            provider=provider,
            api_key=api_key,
        )
        session_dir = session_manager.create_session(options)
        typer.echo(f"Session created at: {session_dir}")

        # Streamlined Initialization: Trigger resume (which triggers planning for EMPTY state)
        orchestrator = container.resolve(IRunPlanUseCase)
        loop_guard = container.resolve(ISessionLoopGuard)

        # Use the actual folder name for session orchestration
        current_session_name = Path(session_dir).name
        turn_count = 0
        while True:
            turn_count += 1
            # Safeguard: prevent infinite loops in non-interactive CI environments
            report = orchestrator.resume(
                session_name=current_session_name,
                interactive=interactive,
            )
            if report is None:
                break

            # In session mode, we do NOT exit on validation failure
            # because the orchestrator triggers an automatic re-plan.
            handle_report_output(
                container, report, no_copy, silent=True, exit_on_failure=False
            )

            cumulative_cost = float(report.metadata.get("cumulative_cost", 0.0))
            if not loop_guard.should_continue(turn_count, cumulative_cost, interactive):
                break

    except Exception as e:
        from teddy_executor.core.domain.models.exceptions import ConfigurationError

        if isinstance(e, ConfigurationError):
            from teddy_executor.core.ports.outbound.config_service import IConfigService

            config_service = container.resolve(IConfigService)
            config_path = config_service.get_config_path()
            typer.echo(f"Error: {e}", err=True)
            typer.echo(f"Please update your configuration at: {config_path}", err=True)
        else:
            typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


def _echo_config_success(container: Container, agent: Optional[str] = None) -> None:
    """Retrieves and echoes the active model and agent configuration on success."""
    from teddy_executor.core.ports.outbound.config_service import IConfigService

    config_service = container.resolve(IConfigService)
    model = config_service.get_setting("llm.model", "unknown")
    msg = f"API key valid! Model: {model}"
    if agent:
        msg += f" | Agent: {agent}"
    typer.echo(msg, err=True)


def _run_cli_preflight_check(container: Container, agent: Optional[str] = None) -> None:
    """Ensures system is configured before starting/resuming a session."""
    from teddy_executor.core.ports.outbound.llm_client import ILlmClient
    from teddy_executor.core.domain.models.exceptions import ConfigurationError
    from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager

    llm_client = container.resolve(ILlmClient)
    # Perform local validation only to ensure fast CLI startup.
    # Remote connectivity is checked lazily by the PlanningService.
    errors = llm_client.validate_config(include_remote=False)

    if agent:
        prompt_manager = container.resolve(IPromptManager)
        if not prompt_manager.get_prompt_content(agent):
            errors.append(f"Agent prompt '{agent}' not found")

    if not errors:
        return

    error_msg = f"Configuration Error: {', '.join(errors)}"
    raise ConfigurationError(error_msg)


def detect_session_context() -> Optional[Dict[str, Sequence[str]]]:
    """Helper to detect turn and session context files."""
    cwd = Path.cwd()
    turn_context = cwd / "turn.context"
    session_context = cwd.parent / "session.context"
    meta_yaml = cwd / "meta.yaml"

    if turn_context.exists() and session_context.exists() and meta_yaml.exists():
        return {
            "Turn": [str(turn_context)],
            "Session": [str(session_context)],
        }
    return None


def handle_plan_generation(container: Container, message: Optional[str]):
    """Logic for the 'plan' command."""
    try:
        # Note: 'plan' command uses the default 'pathfinder' agent if not in a session
        _run_cli_preflight_check(container, agent="pathfinder")
        _echo_config_success(container)

        planning_service: IPlanningUseCase = container.resolve(IPlanningUseCase)
        context_files = detect_session_context()
        cwd = Path.cwd()

        plan_path, _ = planning_service.generate_plan(
            user_message=message, turn_dir=str(cwd), context_files=context_files
        )
        typer.echo(f"Plan generated at: {plan_path}")
    except Exception as e:
        from teddy_executor.core.domain.models.exceptions import ConfigurationError

        if isinstance(e, ConfigurationError):
            from teddy_executor.core.ports.outbound.config_service import IConfigService

            config_service = container.resolve(IConfigService)
            config_path = config_service.get_config_path()
            typer.echo(f"Error: {e}", err=True)
            typer.echo(f"Please update your configuration at: {config_path}", err=True)
        else:
            typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


def handle_context_gathering(container: Container, no_copy: bool):
    """Logic for the 'context' command."""
    context_service: IGetContextUseCase = container.resolve(IGetContextUseCase)
    context_files = detect_session_context()
    # Performance: Formatting context for Markdown doesn't use tokens, so we skip them.
    context_result = context_service.get_context(
        context_files=context_files, include_tokens=False
    )
    formatted_context = format_project_context(context_result)
    echo_and_copy(formatted_context, no_copy=no_copy)


def handle_resume_session(
    container: Container,
    path: Optional[str] = None,
    interactive: bool = True,
    no_copy: bool = False,
):
    """Logic for the 'resume' command."""
    import re
    from teddy_executor.adapters.inbound.cli_helpers import handle_report_output

    try:
        _run_cli_preflight_check(container)
        # For resume, the agent is determined by the session metadata
        _echo_config_success(container)

        session_manager = container.resolve(ISessionManager)

        if path:
            session_name = session_manager.resolve_session_from_path(path)
        else:
            # If no path, first try to resolve from CWD (in case we are inside a session)
            try:
                session_name = session_manager.resolve_session_from_path(
                    str(Path.cwd().resolve())
                )
            except ValueError:
                # If not inside a session, auto-detect the latest session
                session_name = session_manager.get_latest_session_name()

        # Natural Name for display
        display_name = re.sub(r"^\d{8}_\d{6}-", "", session_name)
        typer.echo(f"Resuming session: {display_name}")

        orchestrator = container.resolve(IRunPlanUseCase)
        loop_guard = container.resolve(ISessionLoopGuard)
        turn_count = 0
        while True:
            turn_count += 1
            report = orchestrator.resume(
                session_name=session_name, interactive=interactive
            )
            if not report:
                break

            # In session mode, we do NOT exit on validation failure
            # because the orchestrator triggers an automatic re-plan.
            handle_report_output(
                container, report, no_copy, silent=True, exit_on_failure=False
            )

            cumulative_cost = float(report.metadata.get("cumulative_cost", 0.0))
            if not loop_guard.should_continue(turn_count, cumulative_cost, interactive):
                break

    except Exception as e:
        from teddy_executor.core.domain.models.exceptions import ConfigurationError

        if isinstance(e, ConfigurationError):
            from teddy_executor.core.ports.outbound.config_service import IConfigService

            config_service = container.resolve(IConfigService)
            config_path = config_service.get_config_path()
            typer.echo(f"Error: {e}", err=True)
            typer.echo(f"Please update your configuration at: {config_path}", err=True)
        else:
            typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
