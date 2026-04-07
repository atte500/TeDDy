from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import typer

from teddy_executor.core.domain.models import (
    ExecutionReport,
)

if TYPE_CHECKING:
    from teddy_executor.core.ports.inbound.plan_parser import IPlanParser


app = typer.Typer()


def get_container():
    from teddy_executor.container import get_container as _get_container

    return _get_container()


def _apply_ui_mode_override(container, ui_mode_bool: bool) -> None:
    from teddy_executor.container import register_reviewer

    mode = "tui" if ui_mode_bool else "console"
    register_reviewer(container, ui_mode=mode)


logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
    force=True,
)


@app.callback()
def bootstrap():
    """Ensures the project is anchored to the root and initialized."""
    from teddy_executor.adapters.inbound.cli_helpers import find_project_root
    from teddy_executor.core.ports.outbound.file_system_manager import (
        IFileSystemManager,
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
    from teddy_executor.core.ports.inbound.init import IInitUseCase
    from teddy_executor.core.ports.outbound.config_service import IConfigService
    from teddy_executor.adapters.outbound.yaml_config_adapter import YamlConfigAdapter

    root = str(find_project_root())
    c = get_container()

    # Defensive Guard: Only register if not already configured as an override (e.g. by a test).
    # We allow overwriting default (transient) registrations to ensure project anchoring,
    # but we protect Singletons/Instances (which are typically Mocks or test-specific setups).
    from punq import Scope

    regs = getattr(c.registrations, "_Registry__registrations", {})

    def is_override(service_type) -> bool:
        reg_list = regs.get(service_type)
        if not reg_list:
            return False
        # If any registration is a singleton or has an explicit instance, it's an override
        return any(
            reg.scope == Scope.singleton or hasattr(reg, "instance") for reg in reg_list
        )

    if not is_override(IFileSystemManager):
        c.register(IFileSystemManager, LocalFileSystemAdapter, root_dir=root)
    if not is_override(IRepoTreeGenerator):
        c.register(IRepoTreeGenerator, LocalRepoTreeGenerator, root_dir=root)
    if not is_override(IConfigService):
        c.register(IConfigService, YamlConfigAdapter, root_dir=root)

    c.resolve(IInitUseCase).ensure_initialized()


# Shared Typer options to reduce duplication for jscpd
OPT_NO_COPY = typer.Option(
    False, "--no-copy", help="Do not copy the output to the clipboard."
)
OPT_UI_MODE = typer.Option(
    None, "--tui/--console", help="Force TUI or Console mode.", show_default=False
)


@app.command()
def start(  # noqa: PLR0913
    name: Optional[str] = typer.Argument(None, help="The name of the new session."),
    agent: str = typer.Option("pathfinder", "--agent", help="Agent prompt to use."),
    interactive: bool = typer.Option(
        True, "--interactive/--no-interactive", "-i/-y", help="Interactive mode."
    ),
    no_copy: bool = OPT_NO_COPY,
    ui_mode: Optional[bool] = OPT_UI_MODE,
    message: Optional[str] = typer.Option(
        None, "-m", "--message", help="Instruction for the first turn."
    ),
):
    """
    Initializes a new session directory and bootstraps it for Turn 1.
    """
    from teddy_executor.adapters.inbound.session_cli_handlers import handle_new_session

    container = get_container()
    if ui_mode is not None:
        _apply_ui_mode_override(container, ui_mode)

    handle_new_session(
        container=container,
        name=name,
        agent=agent,
        interactive=interactive,
        no_copy=no_copy,
        message=message,
    )


@app.command()
def plan(
    message: Optional[str] = typer.Option(
        None, "--message", "-m", help="The instructions for the AI."
    ),
):
    """
    Generates a plan.md within the current turn directory.
    """
    from teddy_executor.adapters.inbound.session_cli_handlers import (
        handle_plan_generation,
    )

    handle_plan_generation(get_container(), message)


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

    handle_context_gathering(get_container(), no_copy)


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
    from teddy_executor.adapters.inbound.cli_helpers import echo_and_copy
    from teddy_executor.prompts import find_prompt_content

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
    return get_container().resolve(IPlanParser)


@app.command()
def resume(
    path: Optional[str] = typer.Argument(None, help="Path to session or turn."),
    interactive: bool = typer.Option(
        True, "--interactive/--no-interactive", "-i/-y", help="Interactive mode."
    ),
    no_copy: bool = OPT_NO_COPY,
    ui_mode: Optional[bool] = OPT_UI_MODE,
    message: Optional[str] = typer.Option(
        None, "-m", "--message", help="Instruction to bridge to the next turn."
    ),
):
    """
    Intelligently resumes the last turn of a session or starts a new one.
    """
    from teddy_executor.adapters.inbound.cli_helpers import apply_ui_mode_override
    from teddy_executor.adapters.inbound.session_cli_handlers import (
        handle_resume_session,
    )

    container = get_container()
    if ui_mode is not None:
        apply_ui_mode_override(container, ui_mode)

    handle_resume_session(
        container=container,
        path=path,
        interactive=interactive,
        no_copy=no_copy,
        message=message,
    )


@app.command()
def execute(  # noqa: PLR0913
    plan_file: Optional[Path] = typer.Argument(
        None, help="Root-relative path to the plan file (.md).", show_default=False
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-approve all actions."),
    no_copy: bool = OPT_NO_COPY,
    plan_content: Optional[str] = typer.Option(
        None, "--plan-content", help="Plan content.", show_default=False
    ),
    ui_mode: Optional[bool] = OPT_UI_MODE,
    message: Optional[str] = typer.Option(
        None, "-m", "--message", help="Optional instruction for the report."
    ),
):
    from teddy_executor.adapters.inbound.cli_helpers import (
        apply_ui_mode_override,
        get_plan_content,
        handle_report_output,
    )
    from teddy_executor.core.ports.inbound.plan_parser import InvalidPlanError
    from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase

    report: Optional[ExecutionReport] = None
    interactive_mode = not yes
    start_time = datetime.now(timezone.utc)

    container = get_container()
    if ui_mode is not None:
        apply_ui_mode_override(container, ui_mode)

    try:
        final_plan_content = get_plan_content(plan_content, plan_file)
        orchestrator = container.resolve(IRunPlanUseCase)

        report = orchestrator.execute(
            plan_content=final_plan_content,
            plan_path=str(plan_file) if plan_file else None,
            interactive=interactive_mode,
            message=message,
        )

    except (InvalidPlanError, NotImplementedError) as e:
        from teddy_executor.adapters.inbound.cli_helpers import create_failure_report

        report = create_failure_report(
            e, start_time, container, plan_content=final_plan_content
        )

    handle_report_output(container, report, no_copy)


if __name__ == "__main__":
    app()
