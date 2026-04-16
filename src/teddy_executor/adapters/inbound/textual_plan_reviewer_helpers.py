from __future__ import annotations
import os
import re
from typing import TYPE_CHECKING, Any, Optional, cast

if TYPE_CHECKING:
    from teddy_executor.adapters.inbound.textual_plan_reviewer_app import ReviewerApp
    from teddy_executor.core.domain.models.plan import ActionData
    from teddy_executor.core.domain.models.execution_report import ActionLog

MAX_LABEL_LENGTH = 60


def format_action_log(log: "ActionLog") -> str:
    """
    Formats an ActionLog entry using the global MarkdownReportFormatter to ensure
    exact formatting consistency with the final execution report.
    """
    from datetime import datetime, timezone
    from teddy_executor.core.domain.models.execution_report import (
        ExecutionReport,
        RunSummary,
        RunStatus,
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
    return formatter.format(synthetic_report, is_concise=True)


def extract_status_emoji(raw_status: str) -> str:
    """Extracts the last emoji from a status string."""
    emojis = re.findall(r"[🟢🟡🔴]", raw_status)
    return emojis[-1] if emojis else ""


def handle_mock_editor(path: Any, output: str) -> str:
    """Helper for mock editor output in tests."""
    if path and isinstance(path, (str, os.PathLike)):
        with open(path, "w", encoding="utf-8") as f:
            f.write(output)
    return output


def spawn_editor(cmd: list[str], path: Any) -> None:
    """Spawns an external editor process."""
    import subprocess  # nosec B404

    try:
        subprocess.Popen(  # nosec B603
            cmd + [str(path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:  # nosec B110
        pass


def handle_mock_diff(p_file: Any, before: str, delete_fn: Any) -> bool:
    """Helper for mock diff output in tests."""
    mock_out = os.environ.get("TEDDY_TEST_MOCK_EDITOR_OUTPUT")
    if mock_out:
        with open(p_file, "w", encoding="utf-8") as f:
            f.write(mock_out)
        delete_fn(before)
        return True
    return False


def prepare_after_file(path: Any, proposed: str) -> None:
    """Ensures the 'after' file is ready for diffing/editing."""
    if os.path.exists(path):
        os.chmod(path, 0o644)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(proposed))


def harvest_edit_diff(action: Any, p_file: Any, original: str, proposed: str) -> None:
    """Helper to harvest diff results and update action params."""
    try:
        with open(p_file, "r", encoding="utf-8") as f:
            final: Optional[str] = f.read()
    except Exception:
        final = None
    if final is not None and str(final) != str(proposed):
        action.params["edits"] = [{"find": original, "replace": str(final)}]
        action.params.pop("content", None)


def format_node_label(action: "ActionData") -> str:
    """Format the label for a tree node based on action state."""
    from teddy_executor.core.domain.models.plan import ExecutionStatus

    summary = get_action_summary(action)
    if action.state == ExecutionStatus.RUNNING:
        return f"[blue][RUNNING] {action.type}: {summary}[/]"

    if action.executed:
        color = "green" if action.state.value == "SUCCESS" else "red"
        return f"[{color}][{action.state.value}] {action.type}: {summary}[/]"

    prefix = "[✓]" if action.selected else "[ ]"
    label = f"{prefix} {action.type}: {summary}"
    if action.modified:
        label += " *modified"
    return label


def get_action_summary(action: "ActionData") -> str:
    """Extract a concise summary for the action."""
    summary = action.description or ""
    if not summary:
        params = action.params
        summary = str(
            params.get("path") or params.get("resource") or params.get("command", "")
        )

        if action.type == "PROMPT" and not summary:
            msg = str(params.get("prompt", "")).strip().split("\n")[0]
            summary = msg

    if len(summary) > MAX_LABEL_LENGTH:
        summary = summary[: MAX_LABEL_LENGTH - 3] + "..."
    return summary


def _apply_param_edit(action: Any, key: str, _old_val: Any, new_val: str) -> None:
    """Helper to apply parameter edits back to the action."""
    if action.type == "PROMPT" and key == "response":
        action.user_response = str(new_val)
        return

    # Check if the parameter should be a list based on action type/key
    list_keys = {"queries", "reference_files"}
    if key in list_keys:
        action.params[key] = [v.strip() for v in str(new_val).split(",") if v.strip()]
    else:
        action.params[key] = str(new_val)


async def handle_list_view_selected(
    app: "ReviewerApp", item: Any, update_fn: Any
) -> None:
    """Handle parameter editing when a DetailItem is selected in the right pane."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
        ActionTree,
        PathInputScreen,
        ParameterEditModal,
    )

    node = app.query_one(ActionTree).cursor_node
    if not node or not node.data or not hasattr(item, "data"):
        return

    action, key, val = node.data, item.data.get("key"), item.data.get("val")
    from teddy_executor.core.domain.models.plan import ActionData

    if not isinstance(action, ActionData) or action.executed:
        return

    if action.type == "PROMPT" and key == "prompt":
        return

    if key == "path":
        new_val = await cast(Any, app.push_screen_wait(PathInputScreen(str(val))))
    else:
        if not isinstance(val, (str, int, float, bool, list)) and val is not None:
            return
        v_str = ", ".join(map(str, val)) if isinstance(val, list) else str(val)
        new_val = await cast(
            Any, app.push_screen_wait(ParameterEditModal(f"{key}:", v_str))
        )

    if new_val is not None and str(new_val) != str(val):
        _apply_param_edit(action, key, val, new_val)
        action.modified = True
        app._refresh_node(node)
        update_fn(app, action)


def resolve_action_parameters(action: "ActionData") -> dict[str, Any]:
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
        "timeout": 30.0,
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
        "PRUNE": ["resource", "description"],
        "RESEARCH": ["queries", "description"],
        "PROMPT": ["prompt", "reference_files"],
        "INVOKE": ["agent", "reference_files", "description"],
        "RETURN": ["reference_files", "description"],
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

    if action.type == "PROMPT":
        resolved["response"] = getattr(action, "user_response", None) or ""

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

    if action.type == "PROMPT":
        await _execute_prompt_step(app, action, node, update_fn)
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
    except Exception:
        action.executed, action.state = True, ExecutionStatus.FAILURE
    finally:
        app._refresh_node(node)
        update_fn(app, action)
        app.refresh_bindings()


async def _execute_prompt_step(
    app: ReviewerApp, action: ActionData, node: Any, update_fn: Any
) -> None:
    """Special execution logic for PROMPT actions."""
    from teddy_executor.core.domain.models.plan import ExecutionStatus
    from teddy_executor.core.domain.models.execution_report import (
        ActionStatus,
        ActionLog,
    )
    from teddy_executor.adapters.inbound.textual_plan_reviewer_previews import (
        preview_prompt,
    )

    await preview_prompt(app, action, node)
    if action.modified:
        action.executed, action.state = True, ExecutionStatus.SUCCESS
        action.action_log = ActionLog(
            action_type=action.type,
            params=action.params,
            status=ActionStatus.SUCCESS,
            details={"response": action.user_response},
            failed_command=None,
        )
    else:
        action.state = ExecutionStatus.PENDING
    app._refresh_node(node)
    update_fn(app, action)
    app.refresh_bindings()


def _execute_silently(dispatcher: Any, act: Any) -> Any:
    """Helper to run dispatcher silently."""
    import contextlib
    import io
    import logging

    logger = logging.getLogger("teddy_executor.core.services.action_dispatcher")
    old_level = logger.level
    logger.setLevel(logging.WARNING)
    f = io.StringIO()
    try:
        with contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
            return dispatcher.dispatch_and_execute(act)
    finally:
        logger.setLevel(old_level)


async def handle_edit_action(
    app: ReviewerApp, node: Any, action: Any, update_fn: Any
) -> None:
    """Handles the (e)dit key logic by branching to modals or external editor."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
        ParameterEditModal,
    )
    from teddy_executor.adapters.inbound.textual_plan_reviewer_previews import (
        do_preview_logic,
    )

    if action.type == "EXECUTE":
        val = action.params.get("command", "")
        new_val = await cast(
            Any, app.push_screen_wait(ParameterEditModal("Command:", val))
        )
        if new_val is not None and new_val != val:
            action.params["command"] = new_val
            action.modified = True
            app._refresh_node(node)
            update_fn(app, action)
    elif action.type == "RESEARCH":
        val = action.params.get("queries", [])
        val_str = ", ".join(val) if isinstance(val, list) else str(val)
        new_val = await cast(
            Any,
            app.push_screen_wait(
                ParameterEditModal("Queries (comma separated):", val_str)
            ),
        )
        if new_val is not None and new_val != val_str:
            action.params["queries"] = [
                q.strip() for q in new_val.split(",") if q.strip()
            ]
            action.modified = True
            app._refresh_node(node)
            update_fn(app, action)
    else:
        await do_preview_logic(app, node, action)
        update_fn(app, action)


def handle_revert(app: ReviewerApp, node: Any, update_fn: Any) -> None:
    """Revert manual modifications for the currently highlighted action."""
    action: Optional[ActionData] = node.data
    if action and action.modified:
        action.modified = False
        if hasattr(action, "_original_params"):
            action.params = action._original_params.copy()
        if action.type == "PROMPT":
            action.user_response = None

        ptf = getattr(action, "pending_temp_file", None)
        if isinstance(ptf, str):
            app._system_env.delete_file(ptf)
        action.pending_temp_file = None

        app._refresh_node(node)
        update_fn(app, action)
        app.refresh_bindings()


def harvest_action_content(action: Any, instruction_marker: str) -> None:
    """Harvest modified content from a pending temporary file back to the action."""
    # Type guard for Mocks in tests
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
        elif action.type == "PROMPT":
            marker = instruction_marker.strip()
            if marker in new_content:
                action.user_response = new_content.split(marker)[0].strip()
            else:
                action.user_response = new_content.strip()

        os.remove(action.pending_temp_file)
        action.pending_temp_file = None
    except Exception:  # nosec B110
        pass
