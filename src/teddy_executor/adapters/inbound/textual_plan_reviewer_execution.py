from __future__ import annotations

import contextlib
import io
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from teddy_executor.adapters.inbound.textual_plan_reviewer_app import ReviewerApp
    from teddy_executor.core.domain.models.plan import ActionData
    from teddy_executor.core.domain.models.execution_report import ActionLog


def harvest_action_content(action: Any, instruction_marker: str) -> None:
    """Harvest modified content from a pending temporary file back to the action."""
    import os

    is_valid_path = isinstance(action.pending_temp_file, (str, os.PathLike))
    if not (
        action.pending_temp_file
        and is_valid_path
        and os.path.exists(action.pending_temp_file)
    ):
        return
    try:
        with open(action.pending_temp_file, "r", encoding="utf-8") as f:
            new_content = f.read()
        mapping = {"CREATE": "content", "EXECUTE": "command", "RESEARCH": "queries"}
        if action.type in mapping:
            action.params[mapping[action.type]] = new_content
        os.remove(action.pending_temp_file)
        action.pending_temp_file = None
    except Exception as e:
        import logging

        logging.getLogger(__name__).debug(
            "Failed to harvest action content from %s: %s", action.pending_temp_file, e
        )


def format_action_log(log: ActionLog) -> str:
    """
    Formats an ActionLog entry using the global MarkdownReportFormatter to ensure
    exact formatting consistency with the final execution report.
    """
    from datetime import datetime, timezone

    from teddy_executor.core.domain.models.execution_report import (
        ExecutionReport,
        RunStatus,
        RunSummary,
    )
    from teddy_executor.core.services.markdown_report_formatter import (
        MarkdownReportFormatter,
    )

    now = datetime.now(timezone.utc)
    # Map the action status to a run status for the synthetic report summary
    run_status = RunStatus.SUCCESS
    if log.status.value in ["FAILURE", "SKIPPED"]:
        # Fallback mapping if ActionStatus enum string matches RunStatus
        run_status = getattr(RunStatus, log.status.value, RunStatus.FAILURE)

    synthetic_report = ExecutionReport(
        plan_title=f"{log.action_type} Details",
        run_summary=RunSummary(
            status=run_status,
            start_time=now,
            end_time=now,
        ),
        action_logs=[log],
    )

    formatter = MarkdownReportFormatter()
    return formatter.format(synthetic_report)


def resolve_action_parameters(action: ActionData) -> dict[str, Any]:
    """Resolves the full set of parameters for an action, including defaults."""
    from teddy_executor.core.domain.models.plan import (
        DEFAULT_SIMILARITY_THRESHOLD,
    )

    # Base defaults for all actions
    defaults: dict[str, Any] = {
        "overwrite": False,
        "match_all": False,
        "allow_failure": False,
        "background": False,
        "timeout": 60.0,
        "similarity_threshold": DEFAULT_SIMILARITY_THRESHOLD,
    }

    # Type-specific relevant parameters
    param_map = {
        "CREATE": ["path", "overwrite", "description"],
        "EDIT": ["path", "match_all", "similarity_threshold", "description"],
        "EXECUTE": [
            "command",
            "allow_failure",
            "background",
            "timeout",
            "description",
        ],
        "READ": ["resource", "description"],
        "RESEARCH": ["queries", "description"],
    }

    keys = param_map.get(action.type, [])
    # Hide description from the detail view to reduce clutter
    keys = [k for k in keys if k != "description"]
    resolved: dict[str, Any] = {}
    for key in keys:
        # Use provided value if exists, else fallback to default (if one exists for that key)
        val = action.params.get(key)
        if val is None and key in defaults:
            val = defaults[key]

        # Format lists as comma-separated strings for clean UI display
        if isinstance(val, list):
            val = ", ".join(map(str, val))

        resolved[key] = val

    # After execution, some parameters are hidden from the preview to reduce clutter
    if action.executed:
        # Hide large content/queries/commands once executed; view via 'd'
        for hidden_key in ["content", "queries", "command", "edits"]:
            resolved.pop(hidden_key, None)

        log = action.action_log
        if log:
            resolved["status"] = log.status.value
            if log.failed_command:
                resolved["failed_command"] = log.failed_command
            # Details are intentionally omitted here; they are viewed via 'd' binding

    return resolved


async def orchestrate_execution(app: ReviewerApp, node: Any, update_fn: Any) -> None:
    """Orchestrates the execution of a single action node."""
    from teddy_executor.core.domain.models.plan import ActionData, ExecutionStatus

    action: Any = node.data
    if (
        not isinstance(action, ActionData)
        or action.executed
        or action.state == ExecutionStatus.RUNNING
    ):
        return

    action.state = ExecutionStatus.RUNNING
    app._refresh_node(node)

    try:
        import anyio

        from teddy_executor.core.domain.models.execution_report import ActionStatus

        log = await anyio.to_thread.run_sync(
            _execute_silently, app._action_dispatcher, action
        )

        action.executed, action.action_log = True, log
        action.state = (
            ExecutionStatus.SUCCESS
            if log.status == ActionStatus.SUCCESS
            else ExecutionStatus.FAILURE
        )
    except Exception as e:
        logging.getLogger(__name__).debug("Background execution failed: %s", e)
        action.executed, action.state = True, ExecutionStatus.FAILURE
    finally:
        app._refresh_node(node)
        update_fn(app, action)
        app.refresh_bindings()


def _execute_silently(dispatcher: Any, act: Any) -> Any:
    """Helper to run dispatcher silently."""

    logger = logging.getLogger("teddy_executor.core.services.action_dispatcher")
    old_level = logger.level
    logger.setLevel(logging.WARNING)
    f = io.StringIO()
    try:
        with contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
            return dispatcher.dispatch_and_execute(act)
    finally:
        logger.setLevel(old_level)


async def execute_step_logic(app: ReviewerApp, node: Any, update_fn: Any) -> None:
    """Executes the action with real-time state transitions and feedback."""
    await orchestrate_execution(app, node, update_fn)
