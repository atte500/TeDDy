from pathlib import Path
from typing import Dict, Optional, Sequence
import typer
from punq import Container

from teddy_executor.core.domain.models import RunStatus
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.inbound.planning_use_case import IPlanningUseCase
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.ports.outbound.markdown_report_formatter import (
    IMarkdownReportFormatter,
)
from teddy_executor.adapters.inbound.cli_formatter import format_project_context
from teddy_executor.adapters.inbound.cli_helpers import (
    find_project_root,
    echo_and_copy,
    execute_valid_plan,
)


def handle_new_session(container: Container, name: str, agent: str):
    """Logic for the 'new' command."""
    session_manager: ISessionManager = container.resolve(ISessionManager)
    try:
        session_dir = session_manager.create_session(name=name, agent_name=agent)
        typer.echo(f"Session created at: {session_dir}")
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


def handle_resume_session(container: Container, yes: bool, no_copy: bool):
    """Logic for the 'resume' command."""
    session_name = find_session_name()
    session_manager: ISessionManager = container.resolve(ISessionManager)

    try:
        latest_turn_dir = session_manager.get_latest_turn(session_name)
    except Exception as e:
        typer.echo(f"Error identifying latest turn: {e}", err=True)
        raise typer.Exit(code=1)

    project_root = find_project_root()
    latest_path = project_root / latest_turn_dir
    plan_file = latest_path / "plan.md"
    report_file = latest_path / "report.md"

    if plan_file.exists() and not report_file.exists():
        _execute_pending_plan(container, plan_file, latest_turn_dir, yes, no_copy)
    elif report_file.exists():
        typer.echo(
            "This turn is complete. To start the next turn, please ensure the Turn Transition Algorithm has run (it runs automatically during 'execute')."
        )
    else:
        _trigger_new_plan_loop(container, latest_path)


def _execute_pending_plan(container, plan_file, latest_turn_dir, yes, no_copy):
    from teddy_executor.__main__ import create_parser_for_plan

    final_plan_content = plan_file.read_text(encoding="utf-8")
    parser = create_parser_for_plan(final_plan_content)
    plan = parser.parse(final_plan_content)

    report = execute_valid_plan(
        container,
        plan,
        interactive_mode=not yes,
        parser=parser,
        plan_meta={
            "plan_path": latest_turn_dir + "/plan.md",
            "plan_content": final_plan_content,
        },
    )

    report_formatter = container.resolve(IMarkdownReportFormatter)
    formatted_report = report_formatter.format(report)
    echo_and_copy(formatted_report, no_copy=no_copy)

    if report.run_summary.status in (RunStatus.FAILURE, RunStatus.VALIDATION_FAILED):
        raise typer.Exit(code=1)


def _trigger_new_plan_loop(container, latest_path):
    message = typer.prompt("Enter your instructions for the AI")
    hint = "\n\n*(Stop to reply to this user request and ensure alignment before proceeding)*"
    message += hint

    turn_context = latest_path / "turn.context"
    session_context = latest_path.parent / "session.context"
    meta_yaml = latest_path / "meta.yaml"

    context_files = None
    if turn_context.exists() and session_context.exists() and meta_yaml.exists():
        context_files = {"Turn": [str(turn_context)], "Session": [str(session_context)]}

    planning_service: IPlanningUseCase = container.resolve(IPlanningUseCase)
    try:
        plan_path = planning_service.generate_plan(
            user_message=message, turn_dir=str(latest_path), context_files=context_files
        )
        typer.echo(f"Plan generated at: {plan_path}")
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
