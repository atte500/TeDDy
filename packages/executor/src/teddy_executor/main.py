import sys
import typer
from typing import cast, Optional
from pathlib import Path
import pyperclip

from teddy_executor.core.ports.inbound.run_plan_use_case import RunPlanUseCase
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.services.plan_service import PlanService
from teddy_executor.core.services.context_service import ContextService
from teddy_executor.core.services.action_factory import ActionFactory
from teddy_executor.adapters.inbound.cli_formatter import (
    format_report_as_yaml,
    format_project_context,
)
from teddy_executor.adapters.outbound.shell_adapter import ShellAdapter
from teddy_executor.adapters.outbound.local_file_system_adapter import (
    LocalFileSystemAdapter,
)
from teddy_executor.adapters.outbound.web_scraper_adapter import WebScraperAdapter
from teddy_executor.adapters.outbound.console_interactor import ConsoleInteractorAdapter
from teddy_executor.adapters.outbound.web_searcher_adapter import WebSearcherAdapter
from teddy_executor.adapters.outbound.local_repo_tree_generator import (
    LocalRepoTreeGenerator,
)
from teddy_executor.adapters.outbound.system_environment_inspector import (
    SystemEnvironmentInspector,
)


# ===================================================================
#     CLI Definition (Adapter)
# ===================================================================

app = typer.Typer()


@app.command()
def context(ctx: typer.Context):
    """
    Gathers and displays the project context.
    """
    if not hasattr(ctx, "obj") or not ctx.obj.get("context_service"):
        typer.echo("Error: Core logic (ContextService) not configured.", err=True)
        raise typer.Exit(code=1)

    context_service = cast(IGetContextUseCase, ctx.obj["context_service"])
    context_result = context_service.get_context()
    formatted_context = format_project_context(context_result)
    typer.echo(formatted_context)


@app.command()
def execute(
    ctx: typer.Context,
    plan_file: Optional[Path] = typer.Argument(
        None,
        help="Path to the plan file. If not provided, reads from the clipboard.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Automatically approve all actions without prompting.",
    ),
):
    """
    Executes a plan from a file or the clipboard.
    """
    if not hasattr(ctx, "obj") or not ctx.obj.get("plan_service"):
        typer.echo("Error: Core logic (PlanService) not configured.", err=True)
        raise typer.Exit(code=1)

    plan_service = cast(RunPlanUseCase, ctx.obj["plan_service"])
    plan_content = ""

    if plan_file:
        plan_content = plan_file.read_text()
    else:
        plan_content = pyperclip.paste()
        if not plan_content or not plan_content.strip():
            typer.echo(
                "Error: No plan found in clipboard or clipboard is empty.", err=True
            )
            raise typer.Exit(code=1)

    # NOTE: The 'yes' flag is not yet passed to the plan_service.
    # This will be implemented in a subsequent step when PlanService is updated.
    report = plan_service.execute(plan_content)

    formatted_report = format_report_as_yaml(report)
    typer.echo(formatted_report)

    if report.run_summary.get("status") == "FAILURE":
        raise typer.Exit(code=1)


@app.callback()
def main(ctx: typer.Context):
    """
    Teddy Executor: A CLI for running AI-generated development plans.
    """
    pass


# ===================================================================
#     Composition Root (Main Entry Point)
# ===================================================================


def run():
    """
    This is the main entry point for the application script.
    It is responsible for composing the application layers and running the CLI.
    """
    # 1. Instantiate Adapters and Factories
    shell_adapter = ShellAdapter()
    file_system_adapter = LocalFileSystemAdapter()
    web_scraper_adapter = WebScraperAdapter()
    console_interactor_adapter = ConsoleInteractorAdapter()
    web_searcher_adapter = WebSearcherAdapter()
    repo_tree_generator = LocalRepoTreeGenerator()
    env_inspector = SystemEnvironmentInspector()
    action_factory = ActionFactory()

    # 2. Instantiate Core Logic with its dependencies
    plan_service = PlanService(
        shell_executor=shell_adapter,
        file_system_manager=file_system_adapter,
        web_scraper=web_scraper_adapter,
        action_factory=action_factory,
        user_interactor=console_interactor_adapter,
        web_searcher=web_searcher_adapter,
    )
    context_service = ContextService(
        file_system_manager=file_system_adapter,
        repo_tree_generator=repo_tree_generator,
        environment_inspector=env_inspector,
    )

    services = {
        "plan_service": plan_service,
        "context_service": context_service,
    }

    # 3. Run the CLI with the composed core logic
    app(obj=services)


if __name__ == "__main__":
    typer.echo("Error: This script cannot be run directly.", err=True)
    typer.echo("Please use the 'teddy' command installed by poetry.", err=True)
    sys.exit(1)
