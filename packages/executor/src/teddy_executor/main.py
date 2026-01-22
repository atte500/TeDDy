from pathlib import Path
from typing import Optional

import pyperclip
import punq
import typer

from teddy_executor.core.domain.models import ExecutionReport, RunStatus
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.inbound.run_plan_use_case import RunPlanUseCase
from teddy_executor.core.ports.outbound import (
    IEnvironmentInspector,
    IFileSystemManager,
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
from teddy_executor.core.services.plan_parser import PlanParser
from teddy_executor.adapters.inbound.cli_formatter import (
    format_project_context,
    format_report_as_yaml,
)
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
    container = punq.Container()
    container.register(IShellExecutor, ShellAdapter)
    container.register(IFileSystemManager, LocalFileSystemAdapter)
    container.register(IWebScraper, WebScraperAdapter)
    container.register(IUserInteractor, ConsoleInteractorAdapter)
    container.register(IWebSearcher, WebSearcherAdapter)
    container.register(IRepoTreeGenerator, LocalRepoTreeGenerator)
    container.register(IEnvironmentInspector, SystemEnvironmentInspector)
    container.register(IActionFactory, ActionFactory)
    container.register(PlanParser)
    container.register(ActionDispatcher)
    container.register(RunPlanUseCase, ExecutionOrchestrator)
    container.register(IGetContextUseCase, ContextService)
    return container


app = typer.Typer()
container = create_container()


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
        return found_files[0].read_text()
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
        return plan_file.read_text()

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


@app.command()
def execute(
    plan_file: Optional[Path] = typer.Argument(
        None,
        help="Path to the YAML plan file. If omitted, reads from the clipboard.",
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
        help="The YAML plan content as a string. Overrides plan_file and clipboard.",
        show_default=False,
        rich_help_panel="Advanced Options",
    ),
):
    orchestrator: RunPlanUseCase = container.resolve(RunPlanUseCase)
    report: Optional[ExecutionReport] = None
    interactive_mode = not yes

    try:
        final_plan_content = _get_plan_content(plan_content, plan_file)
        report = orchestrator.execute(
            plan_content=final_plan_content, interactive=interactive_mode
        )

    except pyperclip.PyperclipException as e:
        typer.echo(f"Error accessing clipboard: {e}", err=True)
        raise typer.Exit(code=1)

    if report:
        formatted_report = format_report_as_yaml(report)
        _echo_and_copy(
            formatted_report,
            no_copy=no_copy,
            confirmation_message="Execution report copied to clipboard.",
        )

        if report.run_summary.status == RunStatus.FAILURE:
            raise typer.Exit(code=1)


def run():
    app()


if __name__ == "__main__":
    run()
