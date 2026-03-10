from pathlib import Path
from typing import Dict, Optional, Sequence
import typer
from punq import Container

from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.inbound.planning_use_case import IPlanningUseCase
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.adapters.inbound.cli_formatter import format_project_context
from teddy_executor.adapters.inbound.cli_helpers import (
    echo_and_copy,
)


def handle_new_session(container: Container, name: str, agent: str):
    """Logic for the 'new' command."""
    session_manager: ISessionManager = container.resolve(ISessionManager)
    try:
        session_dir = session_manager.create_session(name=name, agent_name=agent)
        typer.echo(f"Session created at: {session_dir}")

        # Streamlined Initialization: Trigger resume (which triggers planning for EMPTY state)
        orchestrator = container.resolve(IRunPlanUseCase)
        orchestrator.resume(session_name=name)

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


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


def handle_plan_generation(container: Container, message: str):
    """Logic for the 'plan' command."""
    planning_service: IPlanningUseCase = container.resolve(IPlanningUseCase)
    context_files = detect_session_context()
    cwd = Path.cwd()

    try:
        plan_path = planning_service.generate_plan(
            user_message=message, turn_dir=str(cwd), context_files=context_files
        )
        typer.echo(f"Plan generated at: {plan_path}")
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


def handle_context_gathering(container: Container, no_copy: bool):
    """Logic for the 'context' command."""
    context_service: IGetContextUseCase = container.resolve(IGetContextUseCase)
    context_files = detect_session_context()
    context_result = context_service.get_context(context_files=context_files)
    formatted_context = format_project_context(context_result)
    echo_and_copy(formatted_context, no_copy=no_copy)


def find_session_name() -> str:
    """Climbs parents to find the session name."""
    cwd = Path.cwd().resolve()
    # Try to find if we are inside a turn directory
    if (
        cwd.parent.parent.name == "sessions"
        and cwd.parent.parent.parent.name == ".teddy"
    ):
        return cwd.parent.name
    # Or inside a session directory
    elif cwd.parent.name == "sessions" and cwd.parent.parent.name == ".teddy":
        return cwd.name

    typer.echo("Error: Not inside a TeDDy session directory.", err=True)
    raise typer.Exit(code=1)


def handle_resume_session(
    container: Container,
    session_name: Optional[str] = None,
    interactive: bool = True,
    no_copy: bool = False,
):
    """Logic for the 'resume' command."""
    from teddy_executor.adapters.inbound.cli_helpers import handle_report_output

    if not session_name:
        session_name = find_session_name()

    orchestrator = container.resolve(IRunPlanUseCase)

    try:
        report = orchestrator.resume(session_name=session_name, interactive=interactive)
        handle_report_output(container, report, no_copy)
    except Exception as e:
        typer.echo(f"Error during resume: {e}", err=True)
        raise typer.Exit(code=1)
