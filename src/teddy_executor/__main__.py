import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import pyperclip
import typer

from teddy_executor.core.domain.models import (
    ExecutionReport,
    RunStatus,
    RunSummary,
)
from teddy_executor.core.domain.models.plan import Plan
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser, InvalidPlanError
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
from teddy_executor.core.ports.outbound import (
    IFileSystemManager,
    IMarkdownReportFormatter,
    IUserInteractor,
)
from teddy_executor.core.services.action_dispatcher import ActionDispatcher
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser
from teddy_executor.core.services.plan_validator import ValidationError
from teddy_executor.adapters.inbound.cli_formatter import format_project_context
from teddy_executor.container import create_container
from teddy_executor.prompts import find_prompt_content


app = typer.Typer()
container = create_container()

# Configure logging to output to stderr (which Typer handles well)
# Using a simple format since this is intended for user progress updates.
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
    force=True,
)


def _echo_and_copy(
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


@app.command()
def context(
    no_copy: bool = typer.Option(
        False,
        "--no-copy",
        help="Do not copy the output to the clipboard.",
    ),
):
    context_service: IGetContextUseCase = container.resolve(IGetContextUseCase)
    context_result = context_service.get_context()
    formatted_context = format_project_context(context_result)
    _echo_and_copy(formatted_context, no_copy=no_copy)


@app.command(name="get-prompt")
def get_prompt(
    prompt_name: str = typer.Argument(..., help="The name of the prompt to retrieve."),
    no_copy: bool = typer.Option(
        False, "--no-copy", help="Do not copy the output to the clipboard."
    ),
):
    """
    Retrieves and displays the content of a specified prompt.

    Searches for a local override in ./.teddy/prompts/ first.
    """
    prompt_content = find_prompt_content(prompt_name)

    if prompt_content:
        _echo_and_copy(prompt_content, no_copy)
    else:
        # This part will be tested in the next scenario
        typer.echo(f"Error: Prompt '{prompt_name}' not found.", err=True)
        raise typer.Exit(code=1)


def _get_plan_content(
    plan_content_str: Optional[str], plan_file: Optional[Path]
) -> str:
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


def create_parser_for_plan(plan_file: Optional[Path], plan_content: str) -> IPlanParser:
    """
    Factory function to determine which plan parser to use.
    """
    # Legacy YAML plans are deprecated. Only Markdown is supported.
    return MarkdownPlanParser()


def _handle_validation_failure(
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
        run_summary=RunSummary(
            status=RunStatus.VALIDATION_FAILED,
            start_time=start_time,
            end_time=datetime.now(timezone.utc),
        ),
        validation_result=error_messages,
        failed_resources=failed_resources if failed_resources else None,
    )


def _execute_valid_plan(
    plan: Plan, interactive_mode: bool, parser: IPlanParser
) -> ExecutionReport:
    """Executes a plan that has already been parsed and validated."""
    action_dispatcher = container.resolve(ActionDispatcher)
    user_interactor = container.resolve(IUserInteractor)
    file_system_manager = container.resolve(IFileSystemManager)
    orchestrator = ExecutionOrchestrator(
        plan_parser=parser,  # Re-uses the parser
        action_dispatcher=action_dispatcher,
        user_interactor=user_interactor,
        file_system_manager=file_system_manager,
    )
    execution_report = orchestrator.execute(plan=plan, interactive=interactive_mode)
    # Inject the plan title into the report
    return ExecutionReport(
        plan_title=plan.title,
        run_summary=execution_report.run_summary,
        action_logs=execution_report.action_logs,
        validation_result=execution_report.validation_result,
    )


@app.command()
def execute(
    plan_file: Optional[Path] = typer.Argument(
        None,
        help="Path to the plan file (.md). If omitted, reads from clipboard.",
        show_default=False,
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Automatically approve all actions without prompting.",
    ),
    no_copy: bool = typer.Option(
        False,
        "--no-copy",
        help="Do not copy the output to the clipboard.",
    ),
    plan_content: Optional[str] = typer.Option(
        None,
        "--plan-content",
        help="The plan content as a string. Overrides plan_file and clipboard.",
        show_default=False,
        rich_help_panel="Advanced Options",
    ),
):
    report: Optional[ExecutionReport] = None
    interactive_mode = not yes
    start_time = datetime.now(timezone.utc)

    try:
        final_plan_content = _get_plan_content(plan_content, plan_file)
        parser = create_parser_for_plan(plan_file, final_plan_content)

        try:
            plan = parser.parse(final_plan_content)
            plan_validator = container.resolve(IPlanValidator)
            validation_errors = plan_validator.validate(plan)

            if validation_errors:
                report = _handle_validation_failure(plan, validation_errors, start_time)
            else:
                report = _execute_valid_plan(plan, interactive_mode, parser)

        except InvalidPlanError as e:
            report = ExecutionReport(
                plan_title="Invalid Plan",
                run_summary=RunSummary(
                    status=RunStatus.VALIDATION_FAILED,
                    start_time=start_time,
                    end_time=datetime.now(timezone.utc),
                ),
                validation_result=[str(e)],
                action_logs=[],
            )

    except (pyperclip.PyperclipException, NotImplementedError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    if report:
        report_formatter = container.resolve(IMarkdownReportFormatter)
        formatted_report = report_formatter.format(report)

        _echo_and_copy(
            formatted_report,
            no_copy=no_copy,
            confirmation_message="Execution report copied to clipboard.",
        )

        if report.run_summary.status in (
            RunStatus.FAILURE,
            RunStatus.VALIDATION_FAILED,
        ):
            raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
