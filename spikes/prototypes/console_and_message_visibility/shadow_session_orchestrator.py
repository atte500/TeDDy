"""
Shadow file for SessionOrchestrator that adds console visibility features.

Uses composition: wraps a real SessionOrchestrator instance and patches
its execute() method to add:
1. Print emoji + plan title before action execution logs (to stderr).
2. Print user message (if any) after action execution logs (to stderr).

The message is proactively stored in plan metadata before the original execute
call, ensuring it is available regardless of the report assembler's behavior.
"""

from typing import Any, Optional

import typer

from teddy_executor.core.domain.models import ExecutionReport
from teddy_executor.core.domain.models.plan import Plan


def _get_status_emoji(status: Optional[str]) -> str:
    """Map plan status to emoji."""
    mapping = {
        "Draft": "🟢",
        "To De-risk": "🟢",
        "Planned": "🟢",
        "Completed": "🟢",
        "In Progress": "🟡",
        "Blocked": "🔴",
    }
    return mapping.get(status or "", "🟢")


def _echo_visibility(plan: Plan) -> None:
    """Print the emoji + title line to stderr."""
    if plan is not None:
        status = plan.metadata.get("Status") if plan.metadata else None
        emoji = _get_status_emoji(status)
        title = plan.title or ""
        typer.secho(f"{emoji} {title}", fg=typer.colors.GREEN, err=True)


def _echo_user_message(report: ExecutionReport, plan: Plan) -> None:
    """Print the user message (if present) to stderr."""
    user_request = (
        report.metadata.get("user_request")
        or plan.metadata.get("user_request")
    )
    if user_request:
        typer.secho("User Message:", fg=typer.colors.WHITE, err=True)
        typer.secho(user_request, err=True)


def wrap_execute(original_execute):
    """
    Returns a patched execute() that adds visibility features around the original.
    
    If `plan` is None but `plan_path` is provided, it pre-parses the plan
    from the file so that the emoji+title can be printed before the
    original execute runs.

    The `message` parameter is proactively stored in the plan's metadata
    so that it is available for the user message print after execution,
    regardless of whether the report assembler propagates it.
    """
    def patched_execute(self, plan=None, plan_content=None, plan_path=None,
                         interactive=True, message=None, project_context=None):
        # Pre-parse the plan if not already provided
        resolved_plan = plan
        if resolved_plan is None and plan_path is not None:
            try:
                content = self._file_system_manager.read_file(plan_path)
                resolved_plan = self._plan_parser.parse(content, plan_path=plan_path)
            except Exception:
                pass

        # Emoji + Title before action execution
        if resolved_plan is not None:
            _echo_visibility(resolved_plan)

        # Proactively store message in plan metadata so it's available
        # after execution regardless of report assembler behavior
        if message and resolved_plan is not None:
            resolved_plan.metadata["user_request"] = message

        report = original_execute(self, plan=plan, plan_content=plan_content,
                                  plan_path=plan_path, interactive=interactive,
                                  message=message, project_context=project_context)

        # User Message after action execution
        if report is not None and resolved_plan is not None:
            _echo_user_message(report, resolved_plan)

        return report
    return patched_execute
