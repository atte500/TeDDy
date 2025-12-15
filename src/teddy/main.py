import sys
import typer
from typing import cast

from teddy.core.ports.inbound.run_plan_use_case import RunPlanUseCase
from teddy.core.services.plan_service import PlanService
from teddy.core.services.action_factory import ActionFactory
from teddy.adapters.inbound.cli_formatter import format_report_as_markdown
from teddy.adapters.outbound.shell_adapter import ShellAdapter
from teddy.adapters.outbound.file_system_adapter import LocalFileSystemAdapter
from teddy.adapters.outbound.web_scraper_adapter import WebScraperAdapter


# ===================================================================
#     CLI Definition (Adapter)
# ===================================================================

app = typer.Typer()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    Teddy Executor: A tool for running declarative plans.
    Reads a plan from stdin and executes it.
    """
    if ctx.invoked_subcommand is None:
        if not hasattr(ctx, "obj") or not ctx.obj:
            typer.echo("Error: Core logic (PlanService) not configured.", err=True)
            raise typer.Exit(code=1)

        plan_service = cast(RunPlanUseCase, ctx.obj)
        plan_content = sys.stdin.read()
        report = plan_service.execute(plan_content)

        formatted_report = format_report_as_markdown(report)
        typer.echo(formatted_report)

        if report.run_summary.get("status") == "FAILURE":
            raise typer.Exit(code=1)


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
    action_factory = ActionFactory()

    # 2. Instantiate Core Logic with its dependencies
    plan_service = PlanService(
        shell_executor=shell_adapter,
        file_system_manager=file_system_adapter,
        web_scraper=web_scraper_adapter,
        action_factory=action_factory,
    )

    # 3. Run the CLI with the composed core logic
    app(obj=plan_service)


if __name__ == "__main__":
    typer.echo("Error: This script cannot be run directly.", err=True)
    typer.echo("Please use the 'teddy' command installed by poetry.", err=True)
    sys.exit(1)
