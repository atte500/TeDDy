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
from teddy_executor.core.domain.models.plan import Plan
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
