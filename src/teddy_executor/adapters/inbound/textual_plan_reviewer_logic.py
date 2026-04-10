from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, cast

from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
    ParameterEditModal,
)
from teddy_executor.adapters.inbound.textual_plan_reviewer_previews import (
    do_preview_logic,
)
from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
    extract_status_emoji,
)
from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
    format_node_label,
    resolve_action_parameters,
)

if TYPE_CHECKING:
    from teddy_executor.adapters.inbound.textual_plan_reviewer_app import ReviewerApp
    from teddy_executor.core.domain.models.plan import ActionData


# Summary logic moved to textual_plan_reviewer_helpers.py


def on_tree_node_highlighted(app: "ReviewerApp", event: Any) -> None:
    """Handle node highlighting to update the detail view."""
    # event is Tree.NodeHighlighted
    if event.node and getattr(event.node.tree, "id", None) == "left-pane":
        action = event.node.data if not event.node.is_root else None
        _update_detail_view(app, action)
    app.refresh_bindings()


def _update_detail_view(app: "ReviewerApp", action: Optional["ActionData"]):
    """Populate the ParameterDetail view with action parameters or log."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
        ParameterDetail,
        DetailItem,
    )
    from textual.widgets import Label, ListItem

    pane = app.query_one(ParameterDetail)
    pane.clear()
    if not action:
        pane.mount(ListItem(Label("Select an action to view details")))
    else:
        for key, val in resolve_action_parameters(action).items():
            pane.append(DetailItem(key, val))


# Parameter resolution logic moved to textual_plan_reviewer_helpers.py


async def edit_action_logic(
    app: "ReviewerApp", node: Any, action: "ActionData"
) -> None:
    """Handles the (e)dit key logic by branching to modals or external editor."""
    if action.type == "EXECUTE":
        val = action.params.get("command", "")
        new_val = await app.push_screen_wait(ParameterEditModal("Command:", val))
        if new_val is not None and new_val != val:
            action.params["command"] = new_val
            action.modified = True
            app._refresh_node(node)
            _update_detail_view(app, action)
    elif action.type == "RESEARCH":
        val = action.params.get("queries", [])
        if isinstance(val, list):
            val_str = ", ".join(val)
        else:
            val_str = str(val)
        new_val = await app.push_screen_wait(
            ParameterEditModal("Queries (comma separated):", val_str)
        )
        if new_val is not None and new_val != val_str:
            action.params["queries"] = [
                q.strip() for q in new_val.split(",") if q.strip()
            ]
            action.modified = True
            app._refresh_node(node)
            _update_detail_view(app, action)
    # Fallback to existing preview logic for complex types
    else:
        await do_preview_logic(app, node, action)
        _update_detail_view(app, action)


def refresh_node_logic(app: ReviewerApp, node: Any) -> None:
    """Refresh the label and state of a single tree node."""
    if node.data:
        node.label = format_node_label(node.data)


def on_mount_logic(app: Any) -> None:
    """Populate the action tree and set title when the app is mounted."""
    status_raw = app.plan.metadata.get("Status", "")
    status_emoji = extract_status_emoji(status_raw)
    title_parts = [part for part in [status_emoji, app.plan.title] if part]
    app.title = " ".join(title_parts)

    from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
        ActionTree,
    )

    tree = app.query_one(ActionTree)

    tree.root.expand()
    for action in app.plan.actions:
        if not hasattr(action, "_original_params"):
            action._original_params = action.params.copy()
        if action.type == "PRUNE" and not app.plan.is_session:
            continue
        tree.root.add_leaf(format_node_label(action), data=action)

    tree.focus()
    _update_detail_view(app, None)


def check_action_logic(app: ReviewerApp, action_name: str) -> bool:
    """Gate for enabling/disabling bindings based on state."""
    if action_name == "revert":
        from textual.widgets import Tree

        tree = app.query_one(Tree)
        node = tree.cursor_node
        if not node:
            return False
        data: ActionData | None = node.data
        return bool(data and data.modified)
    return True


def toggle_selection_logic(app: ReviewerApp, node: Any) -> None:
    """Toggle action selection when a node is selected."""
    action: Optional["ActionData"] = node.data
    if action is not None and not action.executed:
        action.selected = not action.selected
        app._refresh_node(node)


async def on_list_view_selected_logic(app: "ReviewerApp", item: Any) -> None:
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
    if action.executed or (action.type == "PROMPT" and key == "prompt"):
        return

    if key == "path":
        new_val = await app.push_screen_wait(cast(Any, PathInputScreen(str(val))))
    else:
        if not isinstance(val, (str, int, float, bool, list)) and val is not None:
            return
        v_str = ", ".join(map(str, val)) if isinstance(val, list) else str(val)
        new_val = await app.push_screen_wait(ParameterEditModal(f"{key}:", v_str))

    if new_val is not None and str(new_val) != str(val):
        _apply_param_edit(action, key, val, new_val)
        action.modified = True
        app._refresh_node(node)
        _update_detail_view(app, action)


def _apply_param_edit(action: Any, key: str, old_val: Any, new_val: str) -> None:
    """Helper to apply parameter edits back to the action."""
    if action.type == "PROMPT" and key == "response":
        action.user_response = str(new_val)
    elif isinstance(old_val, list):
        action.params[key] = [v.strip() for v in str(new_val).split(",") if v.strip()]
    else:
        action.params[key] = str(new_val)


def revert_logic(app: "ReviewerApp", node: Any) -> None:
    """Revert manual modifications for the currently highlighted action."""
    action: Optional["ActionData"] = node.data
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
        _update_detail_view(app, action)
        app.refresh_bindings()


async def execute_step_logic(app: "ReviewerApp", node: Any) -> None:
    """Executes the action with real-time state transitions and feedback."""
    from teddy_executor.core.domain.models.plan import ExecutionStatus

    action: Optional["ActionData"] = node.data
    if not action or action.executed or action.state == ExecutionStatus.RUNNING:
        return

    if action.type == "PROMPT":
        await _execute_prompt_step(app, action, node)
        return

    action.state = ExecutionStatus.RUNNING
    app._refresh_node(node)

    try:
        import anyio

        log = await anyio.to_thread.run_sync(
            _execute_silently, app._action_dispatcher, action
        )
        action.executed, action.action_log = True, log
        from teddy_executor.core.domain.models.execution_report import ActionStatus

        action.state = (
            ExecutionStatus.SUCCESS
            if log.status == ActionStatus.SUCCESS
            else ExecutionStatus.FAILURE
        )
    except Exception:
        action.executed, action.state = True, ExecutionStatus.FAILURE
    finally:
        app._refresh_node(node)
        _update_detail_view(app, action)


async def _execute_prompt_step(app: ReviewerApp, action: ActionData, node: Any) -> None:
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
            details="Response captured.",
            failed_command=None,
        )
    else:
        action.state = ExecutionStatus.PENDING
    app._refresh_node(node)
    _update_detail_view(app, action)


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


def toggle_all_logic(app: "ReviewerApp", plan: Any) -> None:
    """Toggle selection for all actions."""
    new_state = any(not action.selected for action in plan.actions)
    for action in plan.actions:
        action.selected = new_state

    from textual.widgets import Tree

    for node in app.query_one(Tree).root.children:
        app._refresh_node(node)
