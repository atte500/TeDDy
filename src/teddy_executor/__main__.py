import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer

from teddy_executor.core.domain.models import (
    ExecutionReport,
    RunStatus,
    RunSummary,
)
from teddy_executor.core.ports.inbound.init import IInitUseCase
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser, InvalidPlanError
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
from teddy_executor.core.ports.outbound.markdown_report_formatter import (
    IMarkdownReportFormatter,
)
from teddy_executor.core.ports.outbound.file_system_manager import (
    FileSystemManager,
)
from teddy_executor.core.ports.outbound.repo_tree_generator import (
    IRepoTreeGenerator,
)
from teddy_executor.adapters.outbound.local_file_system_adapter import (
    LocalFileSystemAdapter,
)
from teddy_executor.adapters.outbound.local_repo_tree_generator import (
    LocalRepoTreeGenerator,
)
from teddy_executor.adapters.inbound.cli_helpers import (
    find_project_root,
    echo_and_copy,
    get_plan_content,
    handle_validation_failure,
    execute_valid_plan,
)
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


@app.callback()
def bootstrap():
    """
    Ensures the project is anchored to the root and initialized.
    """
    project_root = find_project_root()

    # Re-register file system components anchored to the project root
    # This ensures all paths are resolved relative to where the .teddy folder lives.
    container.register(
        FileSystemManager,
        LocalFileSystemAdapter,
        root_dir=str(project_root),
    )
    container.register(
        IRepoTreeGenerator,
        LocalRepoTreeGenerator,
        root_dir=str(project_root),
    )

    init_service: IInitUseCase = container.resolve(IInitUseCase)
    init_service.ensure_initialized()


@app.command()
def new(
    name: str = typer.Argument(..., help="The name of the new session."),
    agent: str = typer.Option(
        "pathfinder", "--agent", help="The name of the agent to use for the session."
    ),
):
    """
    Initializes a new session directory and bootstraps it for Turn 1.
    """
    from teddy_executor.adapters.inbound.session_cli_handlers import handle_new_session

    handle_new_session(container, name, agent)


@app.command()
def plan(
    message: str = typer.Option(
        ..., "--message", "-m", help="The instructions for the AI."
    ),
):
    """
    Generates a plan.md within the current turn directory.
    """
    from teddy_executor.adapters.inbound.session_cli_handlers import (
        handle_plan_generation,
    )

    handle_plan_generation(container, message)


@app.command()
def context(
    no_copy: bool = typer.Option(
        False,
        "--no-copy",
        help="Do not copy the output to the clipboard.",
    ),
):
    """
    Gathers and displays project context (file tree + file contents).

    All operations respect the project's root-relative path conventions.
    """
    from teddy_executor.adapters.inbound.session_cli_handlers import (
        handle_context_gathering,
    )

    handle_context_gathering(container, no_copy)


@app.command(name="get-prompt")
def get_prompt(
    prompt_name: str = typer.Argument(..., help="The name of the prompt to retrieve."),
    no_copy: bool = typer.Option(
        False, "--no-copy", help="Do not copy the output to the clipboard."
    ),
):
    """
    Retrieves and displays the content of a specified prompt.

    Searches for root-relative overrides in ./.teddy/prompts/ before falling back to defaults.
    """
    prompt_content = find_prompt_content(prompt_name)

    if prompt_content:
        echo_and_copy(prompt_content, no_copy)
    else:
        # This part will be tested in the next scenario
        typer.echo(f"Error: Prompt '{prompt_name}' not found.", err=True)
        raise typer.Exit(code=1)


def create_parser_for_plan(plan_content: str) -> IPlanParser:
    """
    Factory function to determine which plan parser to use.
    """
    # Legacy YAML plans are deprecated. Only Markdown is supported.
    return container.resolve(IPlanParser)


@app.command()
def resume(
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
):
    """
    Continues the current session.
    """
    from teddy_executor.adapters.inbound.session_cli_handlers import (
        handle_resume_session,
    )

    handle_resume_session(container, yes, no_copy)


@app.command()
def execute(
    plan_file: Optional[Path] = typer.Argument(
        None,
        help="Root-relative path to the plan file (.md). If omitted, reads from clipboard.",
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
        final_plan_content = get_plan_content(plan_content, plan_file)
        parser = create_parser_for_plan(final_plan_content)

        try:
            plan = parser.parse(final_plan_content)
            plan_validator = container.resolve(IPlanValidator)
            validation_errors = plan_validator.validate(plan)

            if validation_errors:
                report = handle_validation_failure(plan, validation_errors, start_time)
            else:
                report = execute_valid_plan(
                    container,
                    plan,
                    interactive_mode,
                    parser,
                    plan_meta={
                        "plan_path": str(plan_file) if plan_file else None,
                        "plan_content": plan_content,
                    },
                )

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

    except NotImplementedError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

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


if __name__ == "__main__":
    app()
