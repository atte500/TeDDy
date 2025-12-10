import sys
import typer
from typing import cast

from teddy.core.ports.inbound.run_plan_use_case import RunPlanUseCase
from teddy.core.domain.models import ExecutionReport, ActionResult
from teddy.core.services.plan_service import PlanService
from teddy.adapters.outbound.shell_adapter import ShellAdapter
from teddy.adapters.outbound.file_system_adapter import LocalFileSystemAdapter


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

        formatted_report = _format_report_as_markdown(report)
        typer.echo(formatted_report)


def _format_action_result(result: ActionResult) -> str:
    """Formats a single action result into a markdown string."""
    lines = []
    action_type = result.action.action_type

    if action_type == "execute":
        command = result.action.params.get("command", "N/A")
        lines.append(f"### Action: `execute` (`{command}`)")
    elif action_type == "create_file":
        file_path = result.action.params.get("file_path", "N/A")
        lines.append(f"### Action: `create_file` (`{file_path}`)")
    else:
        lines.append(f"### Action: `{action_type}`")

    lines.append(f"- **Status:** {result.status}")
    if result.output:
        lines.append("- **Output:**")
        lines.append("```")
        lines.append(result.output.strip())
        lines.append("```")
    if result.error:
        lines.append("- **Error:**")
        lines.append("```")
        lines.append(result.error.strip())
        lines.append("```")
    return "\n".join(lines)


def _format_report_as_markdown(report: ExecutionReport) -> str:
    """Formats the full execution report into a markdown string."""
    lines = ["# Execution Report"]

    overall_status = report.run_summary.get("status", "UNKNOWN")
    lines.append(f"## Run Summary: {overall_status}")
    lines.append("---")

    lines.append("## Action Logs")
    for result in report.action_logs:
        lines.append(_format_action_result(result))
        lines.append("\n---")

    return "\n".join(lines)


# ===================================================================
#     Composition Root (Main Entry Point)
# ===================================================================


def run():
    """
    This is the main entry point for the application script.
    It is responsible for composing the application layers and running the CLI.
    """
    # 1. Instantiate Adapters
    shell_adapter = ShellAdapter()
    file_system_adapter = LocalFileSystemAdapter()

    # 2. Instantiate Core Logic with its dependencies
    plan_service = PlanService(
        shell_executor=shell_adapter, file_system_manager=file_system_adapter
    )

    # 3. Run the CLI with the composed core logic
    app(obj=plan_service)


if __name__ == "__main__":
    typer.echo("Error: This script cannot be run directly.", err=True)
    typer.echo("Please use the 'teddy' command installed by poetry.", err=True)
    sys.exit(1)
