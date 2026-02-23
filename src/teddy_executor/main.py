import logging
import sys
from pathlib import Path
from typing import Optional

import pyperclip
import punq
import typer

from datetime import datetime, timezone


from teddy_executor.core.domain.models import (
    ExecutionReport,
    RunStatus,
    RunSummary,
)
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
from teddy_executor.core.ports.outbound import (
    IEnvironmentInspector,
    IFileSystemManager,
    IMarkdownReportFormatter,
    IRepoTreeGenerator,
    IShellExecutor,
    IUserInteractor,
    IWebScraper,
    IWebSearcher,
)
from teddy_executor.core.services.action_dispatcher import (
    ActionDispatcher,
    IActionFactory,
)
from teddy_executor.core.services.action_factory import ActionFactory
from teddy_executor.core.services.context_service import ContextService
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser
from teddy_executor.core.services.markdown_report_formatter import (
    MarkdownReportFormatter,
)
from teddy_executor.core.services.plan_validator import PlanValidator
from teddy_executor.adapters.inbound.cli_formatter import format_project_context
from teddy_executor.adapters.outbound.console_interactor import ConsoleInteractorAdapter
from teddy_executor.adapters.outbound.local_file_system_adapter import (
    LocalFileSystemAdapter,
)
from teddy_executor.adapters.outbound.local_repo_tree_generator import (
    LocalRepoTreeGenerator,
)
from teddy_executor.adapters.outbound.shell_adapter import ShellAdapter
from teddy_executor.adapters.outbound.system_environment_inspector import (
    SystemEnvironmentInspector,
)
from teddy_executor.adapters.outbound.web_scraper_adapter import WebScraperAdapter
from teddy_executor.adapters.outbound.web_searcher_adapter import WebSearcherAdapter


def create_container() -> punq.Container:
    """
    Creates and configures the dependency injection container.
    Note: The RunPlanUseCase/ExecutionOrchestrator is not registered here
    because its PlanParser dependency is determined at runtime.
    """
    container = punq.Container()
    container.register(IShellExecutor, ShellAdapter)
    container.register(IFileSystemManager, LocalFileSystemAdapter)
    container.register(IWebScraper, WebScraperAdapter)
    container.register(IUserInteractor, ConsoleInteractorAdapter)
    container.register(IWebSearcher, WebSearcherAdapter)
    container.register(IRepoTreeGenerator, LocalRepoTreeGenerator)
    container.register(IEnvironmentInspector, SystemEnvironmentInspector)
    container.register(IActionFactory, ActionFactory)
    container.register(ActionDispatcher)
    container.register(IPlanValidator, PlanValidator)
    container.register(IMarkdownReportFormatter, MarkdownReportFormatter)
    # PlanParser is now created by the factory
    # RunPlanUseCase is instantiated manually in the `execute` command
    container.register(IGetContextUseCase, ContextService)
    return container


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


def _find_project_root(start_path: Path) -> Optional[Path]:
    """Finds the project root by searching upwards for a .git directory."""
    current_path = start_path.resolve()
    # Check current dir and parents
    for path in [current_path] + list(current_path.parents):
        if (path / ".git").is_dir():
            return path
    return None


def _search_prompt_in_dir(directory: Path, prompt_name: str) -> Optional[str]:
    """Searches a directory for a prompt file and returns its content."""
    if not directory.is_dir():
        return None
    found_files = list(directory.glob(f"{prompt_name}.*"))
    if found_files:
        return found_files[0].read_text(encoding="utf-8")
    return None


def _find_prompt_content(prompt_name: str) -> Optional[str]:
    """
    Finds prompt content by searching in two locations:
    1. A local override directory (`.teddy/prompts/`).
    2. The root-level default prompts directory (`/prompts/`).
    Returns the content as a string, or None if not found.
    """
    # 1. Search for local override
    local_prompt_dir = Path.cwd() / ".teddy" / "prompts"
    if content := _search_prompt_in_dir(local_prompt_dir, prompt_name):
        return content

    # 2. Fallback to root-level prompts
    project_root = _find_project_root(Path.cwd())
    if project_root:
        root_prompt_dir = project_root / "prompts"
        if content := _search_prompt_in_dir(root_prompt_dir, prompt_name):
            return content

    return None


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
    prompt_content = _find_prompt_content(prompt_name)

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
        from teddy_executor.core.ports.inbound.plan_parser import InvalidPlanError

        final_plan_content = _get_plan_content(plan_content, plan_file)
        parser = create_parser_for_plan(plan_file, final_plan_content)

        try:
            plan = parser.parse(final_plan_content)
        except InvalidPlanError as e:
            # Generate a report for parsing errors
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
        else:
            # Pre-flight validation (only if parsing succeeded)
            plan_validator = container.resolve(IPlanValidator)
            validation_result = plan_validator.validate(plan)

            if validation_result:
                failed_resources: dict[str, str] = {}
                error_messages: list[str] = []
                for error in validation_result:
                    error_messages.append(error.message)
                    if error.file_path:
                        try:
                            path = Path(error.file_path)
                            if path.exists():
                                failed_resources[error.file_path] = path.read_text(
                                    encoding="utf-8"
                                )
                        except OSError:
                            pass  # Ignore if reading fails

                report = ExecutionReport(
                    plan_title=plan.title,
                    run_summary=RunSummary(
                        status=RunStatus.VALIDATION_FAILED,
                        start_time=start_time,
                        end_time=datetime.now(timezone.utc),
                    ),
                    validation_result=error_messages,
                    failed_resources=failed_resources if failed_resources else None,
                )
            else:
                # Manually construct the orchestrator
                action_dispatcher = container.resolve(ActionDispatcher)
                user_interactor = container.resolve(IUserInteractor)
                file_system_manager = container.resolve(IFileSystemManager)
                orchestrator = ExecutionOrchestrator(
                    plan_parser=parser,  # Re-uses the parser
                    action_dispatcher=action_dispatcher,
                    user_interactor=user_interactor,
                    file_system_manager=file_system_manager,
                )
                execution_report = orchestrator.execute(
                    plan_content=final_plan_content, interactive=interactive_mode
                )
                # Inject the plan title into the report
                report = ExecutionReport(
                    plan_title=plan.title,
                    run_summary=execution_report.run_summary,
                    action_logs=execution_report.action_logs,
                    validation_result=execution_report.validation_result,
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
