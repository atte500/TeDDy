import difflib
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import pyperclip
import typer
from punq import Container

from teddy_executor.core.domain.models import (
    ExecutionReport,
    RunStatus,
    RunSummary,
)
from teddy_executor.core.domain.models.change_set import ChangeSet
from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.markdown_report_formatter import (
    IMarkdownReportFormatter,
)
from teddy_executor.core.services.plan_validator import ValidationError


def find_project_root() -> Path:
    """
    Locates the project root by climbing up from the CWD until a .teddy directory is found.
    Falls back to CWD if not found.
    """
    current = Path.cwd().resolve()
    for parent in [current] + list(current.parents):
        if (parent / ".teddy").is_dir():
            return parent
    return current


def echo_and_copy(
    content: str,
    no_copy: bool = False,
    confirmation_message: str = "Output copied to clipboard.",
):
    """Prints content to stdout and copies it to the clipboard unless disabled."""
    typer.echo(content)
    if not no_copy:
        try:
            pyperclip.copy(content)
            typer.echo(confirmation_message, err=True)
        except pyperclip.PyperclipException:
            # Silently fail if clipboard is not available.
            pass


def get_plan_content(plan_content_str: Optional[str], plan_file: Optional[Path]) -> str:
    """
    Retrieves the plan content from one of three sources, in order of priority:
    1. A direct string via --plan-content.
    2. A file path.
    3. The system clipboard.
    Exits with an error if the final source is invalid or empty.
    """
    if plan_content_str:
        return plan_content_str

    if plan_file:
        if not plan_file.is_file():
            typer.echo(f"Error: Plan file not found at '{plan_file}'", err=True)
            raise typer.Exit(code=1)
        return plan_file.read_text(encoding="utf-8")

    try:
        plan_from_clipboard = pyperclip.paste()
        if not plan_from_clipboard.strip():
            typer.echo(
                "Error: No plan provided via file or --plan-content, and clipboard is empty.",
                err=True,
            )
            raise typer.Exit(code=1)
        return plan_from_clipboard
    except pyperclip.PyperclipException as e:
        typer.echo(f"Error accessing clipboard: {e}", err=True)
        raise typer.Exit(code=1)


def handle_validation_failure(
    plan: Plan, validation_errors: List[ValidationError], start_time: datetime
) -> ExecutionReport:
    """Creates an ExecutionReport for a validation failure."""
    failed_resources: dict[str, str] = {}
    error_messages: list[str] = []
    for error in validation_errors:
        error_messages.append(error.message)
        if error.file_path:
            try:
                path = Path(error.file_path)
                if path.exists():
                    failed_resources[error.file_path] = path.read_text(encoding="utf-8")
            except OSError:
                pass  # Ignore if reading fails

    return ExecutionReport(
        plan_title=plan.title,
        rationale=plan.rationale,
        original_actions=plan.actions,
        run_summary=RunSummary(
            status=RunStatus.VALIDATION_FAILED,
            start_time=start_time,
            end_time=datetime.now(timezone.utc),
        ),
        validation_result=error_messages,
        failed_resources=failed_resources if failed_resources else None,
    )


def execute_valid_plan(
    container: Container,
    plan: Plan,
    interactive_mode: bool,
    plan_meta: Optional[dict] = None,
) -> ExecutionReport:
    """Executes a plan that has already been parsed and validated."""
    import sys

    orchestrator = container.resolve(IRunPlanUseCase)
    print(f"DEBUG CLI: Resolved orchestrator: {type(orchestrator)}", file=sys.stderr)
    meta = plan_meta or {}
    execution_report = orchestrator.execute(
        plan=plan,
        interactive=interactive_mode,
        plan_path=meta.get("plan_path"),
        plan_content=meta.get("plan_content"),
    )
    return execution_report


def handle_report_output(
    container: Container,
    report: Optional[ExecutionReport],
    no_copy: bool,
) -> None:
    """Formats the report, echoes/copies it, and exits with non-zero if failed."""
    if report:
        report_formatter = container.resolve(IMarkdownReportFormatter)
        formatted_report = report_formatter.format(report)

        echo_and_copy(
            formatted_report,
            no_copy=no_copy,
            confirmation_message="Execution report copied to clipboard.",
        )

        if report.run_summary.status in (
            RunStatus.FAILURE,
            RunStatus.VALIDATION_FAILED,
        ):
            raise typer.Exit(code=1)


def echo_handoff_details(
    action_type: str,
    target_agent: Optional[str],
    resources: List[str],
    message: str,
):
    """Prints formatted handoff details to the terminal."""
    if action_type == "INVOKE":
        typer.secho("--- HANDOFF REQUEST ---", fg=typer.colors.CYAN, err=True)
        typer.echo(
            "The current agent is requesting a handoff to the agent below.\n",
            err=True,
        )
        if target_agent:
            typer.echo(f"▶ Target Agent: {target_agent}", err=True)
        typer.echo(f"▶ Handoff Message:\n{message}\n", err=True)
    else:  # RETURN
        typer.secho("--- HANDOFF NOTIFICATION ---", fg=typer.colors.CYAN, err=True)
        typer.echo(
            "The current agent has completed its task and is returning control.\n",
            err=True,
        )
        typer.echo(f"▶ Return Message:\n{message}\n", err=True)

    if resources:
        typer.echo("▶ Reference Files:", err=True)
        typer.echo("\n".join(resources), err=True)
    typer.echo("", err=True)


def echo_diff_preview(change_set: ChangeSet):
    """Prints a terminal-formatted diff or file preview."""
    if change_set.action_type == "CREATE":
        typer.echo("--- New File Preview ---", err=True)
        typer.echo(f"Path: {change_set.path}", err=True)
        typer.echo("Content:", err=True)
        typer.echo(change_set.after_content, err=True)
        typer.echo("------------------------", err=True)
        return

    diff_generator = difflib.unified_diff(
        change_set.before_content.splitlines(keepends=True),
        change_set.after_content.splitlines(keepends=True),
        fromfile=f"a/{change_set.path.name}",
        tofile=f"b/{change_set.path.name}",
    )

    diff_lines = []
    for line in diff_generator:
        diff_lines.append(line)
        if not line.endswith("\n"):
            diff_lines.append("\n")

    typer.echo("--- Diff ---", err=True)
    typer.echo("".join(diff_lines).rstrip(), err=True)
    typer.echo("------------", err=True)


def echo_skipped_action(action: ActionData, reason: str):
    """Prints a colorized skip notification."""
    message = f"[SKIPPED] {action.type}: {reason}"
    typer.secho(message, fg=typer.colors.YELLOW, err=True)
