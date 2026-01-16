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


@app.command()
def context():
    context_service: IGetContextUseCase = container.resolve(IGetContextUseCase)
    context_result = context_service.get_context()
    formatted_context = format_project_context(context_result)
    typer.echo(formatted_context)


def _get_plan_content(plan_file: Optional[Path]) -> str:
    """
    Retrieves the plan content from a file or the clipboard.
    Exits with an error if the source is invalid.
    """
    plan_content: str
    if plan_file:
        if not plan_file.is_file():
            typer.echo(f"Error: Plan file not found at '{plan_file}'", err=True)
            raise typer.Exit(code=1)
        plan_content = plan_file.read_text()
    else:
        try:
            plan_content = pyperclip.paste()
            if not plan_content.strip():
                typer.echo("Error: Clipboard is empty.", err=True)
                raise typer.Exit(code=1)
        except pyperclip.PyperclipException as e:
            typer.echo(f"Error accessing clipboard: {e}", err=True)
            raise typer.Exit(code=1)
    return plan_content


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
):
    orchestrator: RunPlanUseCase = container.resolve(RunPlanUseCase)
    report: Optional[ExecutionReport] = None
    interactive_mode = not yes

    try:
        plan_content = _get_plan_content(plan_file)
        report = orchestrator.execute(
            plan_content=plan_content, interactive=interactive_mode
        )

    except pyperclip.PyperclipException as e:
        typer.echo(f"Error accessing clipboard: {e}", err=True)
        raise typer.Exit(code=1)

    if report:
        formatted_report = format_report_as_yaml(report)
        typer.echo(formatted_report)
        try:
            pyperclip.copy(formatted_report)
            typer.echo("\nExecution report copied to clipboard.", err=True)
        except pyperclip.PyperclipException:
            pass  # Fail silently if clipboard is not available

        if report.run_summary.status == RunStatus.FAILURE:
            raise typer.Exit(code=1)


def run():
    app()


if __name__ == "__main__":
    run()
