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
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.session_repository import ISessionRepository
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


def _orchestrate_session_loop(
    container: Container,
    session_name: str,
    interactive: bool,
    no_copy: bool,
) -> None:
    """Shared turn loop for start and resume commands."""
    from teddy_executor.adapters.inbound.cli_helpers import handle_report_output

    orchestrator = container.resolve(IRunPlanUseCase)
    session_manager = container.resolve(ISessionManager)

    # Resolve initial state for process-relative guardrails
    latest_turn_path = session_manager.get_latest_turn(session_name)
    try:
        # get_latest_turn returns a path string; the turn ID is the folder name
        initial_turn = int(Path(latest_turn_path).name) if latest_turn_path else 0
    except (ValueError, TypeError):
        # Handle non-numeric turn names or MagicMocks in tests
        initial_turn = 0

    # Resolve initial cost for process-relative guardrails
    initial_cost = session_manager.get_cumulative_cost(session_name)

    loop_guard = container.resolve(
        ISessionLoopGuard, initial_turn=initial_turn, initial_cost=initial_cost
    )

    turn_count = 0
    while True:
        turn_count += 1
        session_name, report = orchestrator.resume(
            session_name=session_name,
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
    try:
        # 0. Ensure project is initialized
        container.resolve(IInitUseCase).ensure_initialized()

        # 1. Pre-flight checks (Fail-fast before user interaction)
        typer.echo("Checking configurations...", err=True)
        _run_cli_preflight_check(container, agent=agent)
        _echo_config_success(container, agent, model=model)

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
        _orchestrate_session_loop(
            container=container,
            session_name=Path(session_dir).name,
            interactive=interactive,
            no_copy=no_copy,
        )

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


def _echo_config_success(
    container: Container,
    agent: Optional[str] = None,
    model: Optional[str] = None,
    actual_model: Optional[str] = None,
) -> None:
    """Retrieves and echoes the active model and agent configuration on success.

    Args:
        container: The DI container with resolved services.
        agent: Optional agent name to display.
        model: Optional model override from CLI. If provided, this takes
               precedence over the config file value.
        actual_model: Optional actual serving model from meta.yaml. If provided,
                      this takes precedence over the model parameter.
    """
    config_service = container.resolve(IConfigService)
    if actual_model:
        resolved_model = actual_model
    elif model:
        resolved_model = model
    else:
        resolved_model = config_service.get_setting("llm.model", "unknown")
    msg = f"API key valid! Model: {resolved_model}"
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


def _resolve_session_name(
    container: Container,
    path: Optional[str] = None,
) -> str:
    """Resolves the session name from a path, CWD, or auto-detection."""
    session_manager = container.resolve(ISessionManager)
    if path:
        return session_manager.resolve_session_from_path(path)
    try:
        return session_manager.resolve_session_from_path(str(Path.cwd().resolve()))
    except ValueError:
        return session_manager.get_latest_session_name()


def _sync_and_display_session_meta(
    container: Container,
    session_name: str,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
) -> None:
    """Reads latest turn meta.yaml, displays actual_model, and syncs config overrides."""
    from teddy_executor.core.ports.outbound.config_service import IConfigService

    session_manager = container.resolve(ISessionManager)
    repository: ISessionRepository = container.resolve(ISessionRepository)
    config_service: IConfigService = container.resolve(IConfigService)

    latest_turn_path = session_manager.get_latest_turn(session_name)
    meta = repository.load_meta(latest_turn_path)
    # Show actual_model if available from previous turn, falling back to model
    _echo_config_success(container, model=model, actual_model=meta.get("actual_model"))

    # Sync latest turn's meta.yaml with current config model/overrides
    config_model = config_service.get_setting("llm.model", "unknown")
    changed = False
    if model:
        meta["model"] = model
        changed = True
    elif config_model != "unknown" and meta.get("model") != config_model:
        meta["model"] = config_model
        changed = True
    if provider:
        meta["provider"] = provider
        changed = True
    if api_key:
        meta["api_key"] = api_key
        changed = True
    if changed:
        repository.save_meta(f"{latest_turn_path}/meta.yaml", meta)


def handle_resume_session(  # noqa: PLR0913
    container: Container,
    path: Optional[str] = None,
    interactive: bool = True,
    no_copy: bool = False,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
):
    """Logic for the 'resume' command."""
    try:
        # 1. Pre-flight checks
        typer.echo("Checking configurations...", err=True)
        _run_cli_preflight_check(container)

        # 2. Resolve session name
        session_name = _resolve_session_name(container, path)

        # 3. Display session path
        session_relative_path = str(Path(".teddy") / "sessions" / session_name)
        typer.echo(f"Resuming session: {session_relative_path}")

        # 4. Display actual_model and sync config overrides
        _sync_and_display_session_meta(
            container, session_name, model=model, provider=provider, api_key=api_key
        )

        # 5. Enter the session loop
        _orchestrate_session_loop(
            container=container,
            session_name=session_name,
            interactive=interactive,
            no_copy=no_copy,
        )

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
