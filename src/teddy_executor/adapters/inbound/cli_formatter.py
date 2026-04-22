import difflib
from typing import List, Optional

import typer

from teddy_executor.core.domain.models import (
    ActionData,
    ChangeSet,
    Plan,
    ProjectContext,
)


def format_project_context(context: ProjectContext) -> str:
    """
    Formats the ProjectContext DTO into a single string for display.
    The actual formatting is now done in the ContextService. This function
    simply combines the pre-formatted parts.
    """
    return f"{context.header}\n{context.content}"


def echo_handoff_details(
    action_type: str,
    target_agent: Optional[str],
    resources: List[str],
    message: str,
):
    """Prints formatted handoff details to the terminal."""
    if action_type == "INVOKE":
        typer.secho("--- HANDOFF REQUEST ---", fg=typer.colors.CYAN, err=True)
        typer.echo(
            "The current agent is requesting a handoff to the agent below.\n",
            err=True,
        )
        if target_agent:
            typer.echo(f"▶ Target Agent: {target_agent}", err=True)
        typer.echo(f"▶ Handoff Message:\n{message}\n", err=True)
    else:  # RETURN
        typer.secho("--- HANDOFF NOTIFICATION ---", fg=typer.colors.CYAN, err=True)
        typer.echo(
            "The current agent has completed its task and is returning control.\n",
            err=True,
        )
        typer.echo(f"▶ Return Message:\n{message}\n", err=True)

    if resources:
        typer.echo("▶ Reference Files:", err=True)
        typer.echo("\n".join(resources), err=True)
    typer.echo("", err=True)


def echo_diff_preview(change_set: ChangeSet):
    """Prints a terminal-formatted diff or file preview."""
    if change_set.action_type == "CREATE":
        typer.echo("--- New File Preview ---", err=True)
        typer.echo(f"Path: {change_set.path}", err=True)
        typer.echo("Content:", err=True)
        typer.echo(change_set.after_content, err=True)
        typer.echo("------------------------", err=True)
        return

    diff_generator = difflib.unified_diff(
        change_set.before_content.splitlines(keepends=True),
        change_set.after_content.splitlines(keepends=True),
        fromfile=f"a/{change_set.path.name}",
        tofile=f"b/{change_set.path.name}",
    )

    diff_lines = []
    for line in diff_generator:
        diff_lines.append(line)
        if not line.endswith("\n"):
            diff_lines.append("\n")

    typer.echo("--- Diff ---", err=True)
    typer.echo("".join(diff_lines).rstrip(), err=True)
    typer.echo("------------", err=True)


def echo_plan_summary(plan: Plan):
    """Prints a summary of the plan's actions to the terminal."""
    header = f'\n▶ Reviewing Plan: "{plan.title}"'
    typer.secho(header, fg=typer.colors.CYAN, bold=True, err=True)
    typer.echo("-" * 68, err=True)

    counts: dict[str, int] = {}
    for action in plan.actions:
        counts[action.type] = counts.get(action.type, 0) + 1

    typer.echo("\n Action Plan:", err=True)
    for action_type in sorted(counts.keys()):
        count = counts[action_type]
        label = "action" if count == 1 else "actions"
        typer.echo(f"  - {action_type}: {count} {label}", err=True)
    typer.echo("\n" + "-" * 68, err=True)


def echo_skipped_action(action: ActionData, reason: str):
    """Prints a colorized skip notification."""
    message = f"[SKIPPED] {action.type}: {reason}"
    typer.secho(message, fg=typer.colors.YELLOW, err=True)


def style_text(text: str, style: str) -> str:
    """Wraps text in Rich style tags."""
    return f"[{style}]{text}[/]"
