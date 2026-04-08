from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, cast

from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
    ParameterEditModal,
    StatusBar,
)
from teddy_executor.adapters.inbound.textual_plan_reviewer_previews import (
    do_preview_logic,
    extract_status_emoji,
)
from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
    get_action_summary,
    resolve_action_parameters,
)

if TYPE_CHECKING:
    from teddy_executor.adapters.inbound.textual_plan_reviewer_app import ReviewerApp
    from teddy_executor.core.domain.models.plan import ActionData


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
        return

    # If executed, show the log
    if action.executed and action.action_log:
        log = action.action_log
        pane.mount(ListItem(Label(f"[bold]LOG:[/] {action.type}")))
        pane.mount(ListItem(Label(f"[bold]status:[/] {log.status}")))
        if log.details:
            pane.mount(ListItem(Label(f"[bold]details:[/] {log.details}")))
        if log.failed_command:
            pane.mount(ListItem(Label(f"[bold]failed_cmd:[/] {log.failed_command}")))
        return

    # Show resolved parameters
    resolved = resolve_action_parameters(action)
    for key, val in resolved.items():
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
    elif action.type == "RESEARCH":
        val = action.params.get("queries", "")
        new_val = await app.push_screen_wait(ParameterEditModal("Queries:", val))
        if new_val is not None and new_val != val:
            action.params["queries"] = new_val
            action.modified = True
            app._refresh_node(node)
    # Fallback to existing preview logic for complex types
    else:
        await do_preview_logic(app, node, action)


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

    tree = app.query_one(ActionTree)
    node = tree.cursor_node
    if not node or not node.data or not hasattr(item, "data"):
        return

    action: ActionData = node.data
    key = item.data.get("key")
    val = item.data.get("val")

    # Only allow editing if the action hasn't been executed yet
    if action.executed:
        return

    if key == "path":
        new_val = await app.push_screen_wait(cast(Any, PathInputScreen(str(val))))
    else:
        # Don't allow editing complex/derived params via simple modal (e.g. 'edits')
        if not isinstance(val, (str, int, float, bool)) and val is not None:
            return
        new_val = await app.push_screen_wait(ParameterEditModal(f"{key}:", str(val)))

    if new_val is not None and str(new_val) != str(val):
        action.params[key] = str(new_val)
        action.modified = True
        app._refresh_node(node)
        _update_detail_view(app, action)


def revert_logic(app: "ReviewerApp", node: Any) -> None:
    """Revert manual modifications for the currently highlighted action."""
    action: Optional["ActionData"] = node.data
    if action and action.modified:
        action.modified = False
        app._refresh_node(node)
        app.refresh_bindings()


async def execute_step_logic(app: "ReviewerApp", node: Any) -> None:
    """Executes the action with real-time state transitions and feedback."""
    from teddy_executor.core.domain.models.plan import ExecutionStatus
    from teddy_executor.core.domain.models.execution_report import (
        ActionStatus,
        ActionLog,
    )
    from teddy_executor.adapters.inbound.textual_plan_reviewer_previews import (
        preview_prompt,
    )
    import anyio

    action: Optional["ActionData"] = node.data
    if not action or action.executed or action.state == ExecutionStatus.RUNNING:
        return

    # Special Case: Manual PROMPT execution triggers the editor reply loop
    if action.type == "PROMPT":
        await preview_prompt(app, action, node)
        if action.modified:
            action.executed = True
            action.state = ExecutionStatus.SUCCESS
            action.action_log = ActionLog(
                action_type=action.type,
                params=action.params,
                status=ActionStatus.SUCCESS,
                details="Response captured.",
                failed_command=None,
            )
            app._refresh_node(node)
        else:
            action.state = ExecutionStatus.PENDING
            app._refresh_node(node)
        return

    status_bar = cast(StatusBar, app.query_one("StatusBar"))

    # Phase 1: Set to RUNNING
    action.state = ExecutionStatus.RUNNING
    app._refresh_node(node)
    status_bar.update_status(f"RUNNING: {action.type}")

    try:
        # Phase 2: Real execution via ActionDispatcher
        # Use anyio.to_thread for potentially blocking filesystem/shell operations
        log = await anyio.to_thread.run_sync(
            app._action_dispatcher.dispatch_and_execute, action
        )

        # Phase 3: Finalize state based on result
        action.executed = True
        action.action_log = log
        if log.status == ActionStatus.SUCCESS:
            action.state = ExecutionStatus.SUCCESS
            status_bar.update_status(f"SUCCESS: {action.type}")
        else:
            action.state = ExecutionStatus.FAILURE
            error_msg = str(log.details) if log.details else "Unknown error"
            status_bar.update_status(f"FAILURE: {action.type} - {error_msg}")
    except Exception as e:
        # Phase 3: Catch-all for dispatch errors
        action.executed = True
        action.state = ExecutionStatus.FAILURE
        status_bar.update_status(f"FAILURE: {action.type} - {str(e)}")
    finally:
        app._refresh_node(node)


def toggle_all_logic(app: "ReviewerApp", plan: Any) -> None:
    """Toggle selection for all actions."""
    any_unselected = any(not action.selected for action in plan.actions)
    new_state = any_unselected

    for action in plan.actions:
        action.selected = new_state

    # Refresh all child nodes in the tree
    from textual.widgets import Tree

    tree = app.query_one(Tree)
    for node in tree.root.children:
        app._refresh_node(node)
