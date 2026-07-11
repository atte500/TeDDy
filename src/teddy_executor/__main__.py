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


@app.callback(invoke_without_command=True)
def main_callback(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show the installed version.",
        is_eager=True,
    ),
) -> None:
    if version:
        from importlib.metadata import version as _get_version

        installed = _get_version("teddy-cli")
        typer.echo(f"TeDDy v{installed}")
        raise typer.Exit()


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


def _ensure_project_initialized(container, root_dir: str | None = None) -> None:
    """Lazily performs project anchoring and initialization.

    If root_dir is provided, uses that path as the root. Otherwise, finds
    the nearest parent containing .teddy/ via find_project_root().
    """
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
    from punq import Scope

    if root_dir is None:
        root = str(find_project_root())
    else:
        root = root_dir
    c = container

    regs = getattr(c.registrations, "_Registry__registrations", {})

    def is_override(service_type) -> bool:
        reg_list = regs.get(service_type)
        return any(
            reg.scope == Scope.singleton or hasattr(reg, "instance")
            for reg in (reg_list or [])
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
    agent: str = typer.Option(
        "pathfinder", "--agent", "-a", help="Agent prompt to use."
    ),
    yolo: bool = typer.Option(
        False, "--yolo", "-y", help="Auto-approve all actions (non-interactive mode)."
    ),
    yes: bool = typer.Option(False, "--yes", hidden=True),
    no_interactive: bool = typer.Option(False, "--no-interactive", hidden=True),
    non_interactive: bool = typer.Option(False, "--non-interactive", hidden=True),
    no_copy: bool = OPT_NO_COPY,
    ui_mode: Optional[bool] = OPT_UI_MODE,
    message: Optional[str] = typer.Option(
        None, "-m", "--message", help="Instruction for the first turn."
    ),
    context: Optional[str] = typer.Option(
        None,
        "--context",
        "-c",
        help="Comma-separated list of additional files/dirs for context.",
    ),
    model: Optional[str] = typer.Option(None, "--model", help="LLM model override."),
    provider: Optional[str] = typer.Option(
        None, "--provider", help="LLM provider override."
    ),
    api_key: Optional[str] = typer.Option(
        None, "--api-key", help="LLM API key override."
    ),
):
    """
    Initializes a new session directory and bootstraps it for Turn 1.
    """
    from teddy_executor.adapters.inbound.session_cli_handlers import handle_new_session

    container = get_container()
    _ensure_project_initialized(container)
    if ui_mode is not None:
        _apply_ui_mode_override(container, ui_mode)

    additional_context = context.split(",") if context else None

    handle_new_session(
        container=container,
        name=name,
        agent=agent,
        interactive=not (yolo or yes or no_interactive or non_interactive),
        no_copy=no_copy,
        message=message,
        additional_context=additional_context,
        model=model,
        provider=provider,
        api_key=api_key,
    )


init_app = typer.Typer()


@init_app.callback(invoke_without_command=True)
def init_callback(ctx: typer.Context):
    """
    Initializes the .teddy directory and pre-warms heavy imports for faster startup.
    """
    from teddy_executor.adapters.inbound.cli_helpers import prewarm_imports
    from teddy_executor.core.ports.inbound.init import IInitUseCase

    container = get_container()
    _ensure_project_initialized(container, root_dir=str(Path.cwd()))
    prewarm_imports()
    # Auto-login would trigger here once `teddy login` is implemented (no-op for now)
    if ctx.invoked_subcommand is not None:
        # A subcommand (e.g., prompts, config) will handle its own initialization
        # and output. Skip the full summary to avoid conflicting messages.
        return
    init_use_case = container.resolve(IInitUseCase)
    summary = init_use_case.ensure_initialized()
    typer.echo(f"TeDDy initialized in .teddy folder. {summary}")


@init_app.command()
def prompts():
    """
    Overwrites bundled prompt XMLs in .teddy/prompts/ with defaults.
    """
    from teddy_executor.core.ports.inbound.init import IInitUseCase

    container = get_container()
    init_use_case = container.resolve(IInitUseCase)
    status = init_use_case.ensure_prompts_initialized(overwrite=True)
    typer.echo(status)


@init_app.command()
def config():
    """
    Overwrites config.yaml, .gitignore, and init.context with defaults.
    """
    from teddy_executor.core.ports.inbound.init import IInitUseCase

    container = get_container()
    init_use_case = container.resolve(IInitUseCase)
    status = init_use_case.ensure_config_initialized(overwrite=True)
    typer.echo(status)


app.add_typer(
    init_app,
    name="init",
    help="Initialize .teddy directory, prompts, or configuration.",
)


@app.command()
def version() -> None:
    """Show the installed version."""
    from importlib.metadata import version as _get_version

    installed = _get_version("teddy-cli")
    typer.echo(f"TeDDy v{installed}")


@app.command()
def update(
    experimental: bool = typer.Option(
        False,
        "--experimental",
        help="Check and upgrade from TestPyPI instead of PyPI.",
    ),
):
    """Checks PyPI for the latest version of TeDDy and displays upgrade
    instructions. Does not upgrade automatically."""
    from teddy_executor.core.services.update_checker import (
        get_current_version,
        fetch_latest_version,
        compare_versions,
        is_prerelease,
        PYPI_URL,
        TEST_PYPI_URL,
    )

    index_url = TEST_PYPI_URL if experimental else PYPI_URL
    # When experimental, include prerelease versions (TestPyPI only has dev releases)
    latest = fetch_latest_version(index_url, stable_only=not experimental)

    if latest is None:
        typer.echo("Could not check for updates: network error.")
        return

    current = get_current_version()

    needs_update = compare_versions(current, latest)
    is_channel_switch = False
    if not needs_update:
        # If current is a pre-release and the latest is stable, allow downgrade
        # to the stable channel
        if is_prerelease(current) and not is_prerelease(latest):
            is_channel_switch = True

    if not needs_update and not is_channel_switch:
        typer.echo(f"You are already running the latest version ({current}).")
        return

    if is_channel_switch:
        typer.echo(f"You are running the latest experimental version ({current}).")
        typer.echo(
            "To switch to the stable release, run: uv tool install teddy-cli --force"
        )
        typer.echo("To apply prompt updates, run: teddy init prompts")
    elif experimental:
        typer.echo(f"A new experimental version {latest} is available.")
        typer.echo(
            "To upgrade, run: uv tool install teddy-cli --pre --force --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ --index-strategy unsafe-best-match"
        )
        typer.echo("To apply prompt updates, run: teddy init prompts")
    else:
        typer.echo(f"A new version {latest} is available.")
        typer.echo("To upgrade, run: uv tool upgrade teddy-cli")
        typer.echo("To apply prompt updates, run: teddy init prompts")


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

    container = get_container()
    _ensure_project_initialized(container)
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
    from teddy_executor.adapters.inbound.cli_helpers import echo_and_copy
    from teddy_executor.prompts import find_prompt_content, list_prompt_names

    prompt_content = find_prompt_content(prompt_name)

    if prompt_content:
        echo_and_copy(prompt_content, no_copy)
    else:
        available = list_prompt_names()
        if available:
            msg = f"Error: Prompt '{prompt_name}' not found. Available prompts: {', '.join(available)}"
        else:
            msg = f"Error: Prompt '{prompt_name}' not found."
        typer.echo(msg, err=True)
        raise typer.Exit(code=1)


def create_parser_for_plan(plan_content: str) -> IPlanParser:
    """
    Factory function to determine which plan parser to use.
    """
    # Legacy YAML plans are deprecated. Only Markdown is supported.
    return get_container().resolve(IPlanParser)


@app.command()
def resume(  # noqa: PLR0913
    path: Optional[str] = typer.Argument(None, help="Path to session or turn."),
    yolo: bool = typer.Option(
        False, "--yolo", "-y", help="Auto-approve all actions (non-interactive mode)."
    ),
    yes: bool = typer.Option(False, "--yes", hidden=True),
    no_interactive: bool = typer.Option(False, "--no-interactive", hidden=True),
    non_interactive: bool = typer.Option(False, "--non-interactive", hidden=True),
    no_copy: bool = OPT_NO_COPY,
    ui_mode: Optional[bool] = OPT_UI_MODE,
    model: Optional[str] = typer.Option(None, "--model", help="LLM model override."),
    provider: Optional[str] = typer.Option(
        None, "--provider", help="LLM provider override."
    ),
    api_key: Optional[str] = typer.Option(
        None, "--api-key", help="LLM API key override."
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
    _ensure_project_initialized(container)
    if ui_mode is not None:
        apply_ui_mode_override(container, ui_mode)

    handle_resume_session(
        container=container,
        path=path,
        interactive=not (yolo or yes or no_interactive or non_interactive),
        no_copy=no_copy,
        model=model,
        provider=provider,
        api_key=api_key,
    )


@app.command()
def execute(  # noqa: PLR0913
    plan_file: Optional[Path] = typer.Argument(
        None, help="Root-relative path to the plan file (.md).", show_default=False
    ),
    yolo: bool = typer.Option(
        False, "--yolo", "-y", help="Auto-approve all actions (non-interactive mode)."
    ),
    yes: bool = typer.Option(False, "--yes", hidden=True),
    no_interactive: bool = typer.Option(False, "--no-interactive", hidden=True),
    non_interactive: bool = typer.Option(False, "--non-interactive", hidden=True),
    no_copy: bool = OPT_NO_COPY,
    plan_content: Optional[str] = typer.Option(
        None, "--plan-content", help="Plan content.", show_default=False
    ),
    ui_mode: Optional[bool] = OPT_UI_MODE,
    message: Optional[str] = typer.Option(
        None, "-m", "--message", help="Optional instruction for the report."
    ),
):
    """
    Executes a Markdown plan file (from path or clipboard) and generates an execution report.
    """
    from teddy_executor.adapters.inbound.cli_helpers import (
        apply_ui_mode_override,
        get_plan_content,
        handle_report_output,
    )
    from teddy_executor.core.ports.inbound.plan_parser import InvalidPlanError
    from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase

    report: Optional[ExecutionReport] = None
    interactive_mode = not (yolo or yes or no_interactive or non_interactive)
    start_time = datetime.now(timezone.utc)

    container = get_container()
    _ensure_project_initialized(container)
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
