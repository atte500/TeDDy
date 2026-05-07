from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from teddy_executor.adapters.inbound.textual_plan_reviewer_execution import (
    resolve_action_parameters,
)
from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
    format_node_label,
)

if TYPE_CHECKING:
    from teddy_executor.adapters.inbound.textual_plan_reviewer_app import ReviewerApp
    from teddy_executor.core.domain.models.plan import ActionData


ALLOWED_RATIONALE_SECTIONS = [
    "Synthesis",
    "Justification",
    "Expectation",
    "State Dashboard",
]

# Tree Node Identifiers
CONTEXT_ROOT = "CONTEXT_ROOT"
SYSTEM_LABEL = "SYSTEM_LABEL"
SESSION_LABEL = "SESSION_LABEL"
TURN_LABEL = "TURN_LABEL"
RATIONALE_ROOT = "RATIONALE_ROOT"
ACTION_PLAN_ROOT = "ACTION_PLAN_ROOT"


# Summary logic moved to textual_plan_reviewer_helpers.py


def on_tree_node_highlighted(app: "ReviewerApp", event: Any) -> None:
    """Handle node highlighting to update the detail view."""
    # event is Tree.NodeHighlighted
    if event.node and getattr(event.node.tree, "id", None) == "left-pane":
        # Root node has no data usually, but our virtual roots do
        _update_detail_view(app, event.node.data)
    app.refresh_bindings()


def _update_detail_view(app: ReviewerApp, data: Any):
    """Populate the ParameterDetail view or Rationale view."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
        ParameterDetail,
        DetailItem,
    )
    from textual.widgets import Label, ListItem, ContentSwitcher, Markdown

    switcher = app.query_one(ContentSwitcher)
    pane = app.query_one(ParameterDetail)

    from teddy_executor.core.domain.models.project_context import ContextItem

    # Handle Context items and roots
    if (
        data in (CONTEXT_ROOT, SYSTEM_LABEL, SESSION_LABEL, TURN_LABEL)
        or isinstance(data, ContextItem)
        or (isinstance(data, dict) and data.get("type") == "SYSTEM_PROMPT")
    ):
        switcher.current = "params-view"
        pane.clear()
        from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
            populate_context_detail,
        )

        populate_context_detail(app, pane, data)
        return

    if isinstance(data, dict) and data.get("type") == "RATIONALE_SECTION":
        switcher.current = "rationale-view"
        app.query_one("#rationale-content", Markdown).update(data["content"])
        return

    # Default to parameter view for everything else
    switcher.current = "params-view"
    pane.clear()

    if not data:
        pane.mount(ListItem(Label("Select an item to view details")))
        return

    if data == RATIONALE_ROOT:
        # Prevent race condition: don't update metadata if user has already moved cursor
        from textual.widgets import Tree

        tree = app.query_one(Tree)
        if tree.cursor_node and tree.cursor_node.data != RATIONALE_ROOT:
            return

        # Check both cases as metadata keys can vary
        agent = (
            app.plan.metadata.get("Agent")
            or app.plan.metadata.get("agent")
            or "Unknown"
        )
        plan_type = (
            app.plan.metadata.get("Plan Type")
            or app.plan.metadata.get("plan_type")
            or "Development"
        )
        status = (
            app.plan.metadata.get("Status") or app.plan.metadata.get("status") or "N/A"
        )
        pane.append(DetailItem("Agent", agent))
        pane.append(DetailItem("Plan Type", plan_type))
        pane.append(DetailItem("Status", status))
    elif data == ACTION_PLAN_ROOT:
        pane.mount(ListItem(Label("Select an action below to view details")))
    else:
        # data is likely ActionData
        from teddy_executor.core.domain.models.plan import ActionData

        if isinstance(data, ActionData):
            for key, val in resolve_action_parameters(data).items():
                # Stringify Enum values for clean display
                val_str = val.value if hasattr(val, "value") else str(val)
                pane.append(DetailItem(key, val_str))
        else:
            pane.mount(ListItem(Label("Select an item to view details")))


async def edit_action_logic(app: ReviewerApp, node: Any, action: ActionData) -> None:
    """Handles the (e)dit key logic by branching to modals or external editor."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_editor import (
        handle_edit_action,
    )

    await handle_edit_action(app, node, action, _update_detail_view)


def refresh_node_logic(app: ReviewerApp, node: Any) -> None:
    """Refresh the label and state of a single tree node."""
    from teddy_executor.core.domain.models.plan import ActionData
    from teddy_executor.core.domain.models.project_context import ContextItem
    from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
        format_context_item_label,
    )

    if isinstance(node.data, ActionData):
        node.label = format_node_label(node.data)
    elif isinstance(node.data, ContextItem):
        node.label = format_context_item_label(node.data)


def on_mount_logic(app: Any) -> None:
    """Delegate tree population and title setting."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
        handle_mount_logic,
    )

    handle_mount_logic(app, _update_detail_view)


def check_action_logic(app: ReviewerApp, action_name: str) -> bool:
    """Gate for enabling/disabling bindings based on state."""
    from textual.widgets import Tree
    from teddy_executor.core.domain.models.plan import ActionData

    tree = app.query_one(Tree)
    node = tree.cursor_node

    # Navigation and universal actions are always allowed
    if action_name in (
        "focus_right",
        "focus_left",
        "jump_next",
        "jump_prev",
        "cancel",
        "submit",
        "view_plan",
        "add_message",
        "toggle_all",
    ):
        return True

    from teddy_executor.core.domain.models.project_context import ContextItem

    if not node:
        return False

    if isinstance(node.data, ContextItem):
        # Context items only support toggling (space) and universal navigation
        return action_name in (
            "toggle_selection",
            "focus_right",
            "focus_left",
            "jump_next",
            "jump_prev",
            "cancel",
        )

    if not isinstance(node.data, ActionData):
        return False

    data = cast(ActionData, node.data)

    data = cast(ActionData, node.data)
    results = {
        "execute_step": not data.executed,
        "edit_details": not data.executed,
        "view_details": bool(data.executed),
        "revert": bool(data.modified) and not data.executed,
    }
    return results.get(action_name, True)


def toggle_selection_logic(app: ReviewerApp, node: Any) -> None:
    """Toggle action selection when a node is selected."""
    from teddy_executor.core.domain.models.plan import ActionData
    from teddy_executor.core.domain.models.project_context import ContextItem

    data: Any = node.data
    if isinstance(data, ActionData) and not data.executed:
        data.selected = not data.selected
        app._refresh_node(node)
    elif isinstance(data, ContextItem):
        data.selected = not data.selected
        app._refresh_node(node)


async def on_list_view_selected_logic(app: ReviewerApp, item: Any) -> None:
    """Handle parameter editing when a DetailItem is selected in the right pane."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_editor import (
        handle_list_view_selected,
    )

    await handle_list_view_selected(app, item, _update_detail_view)


def revert_logic(app: ReviewerApp, node: Any) -> None:
    """Revert manual modifications for the currently highlighted action."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
        handle_revert,
    )

    handle_revert(app, node, _update_detail_view)


async def execute_step_logic(app: ReviewerApp, node: Any) -> None:
    """Executes the action with real-time state transitions and feedback."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_execution import (
        execute_step_logic as exec_logic,
    )

    await exec_logic(app, node, _update_detail_view)


async def view_details_logic(app: "ReviewerApp") -> None:
    """View full execution logs for the currently highlighted action."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_previews import (
        view_details_handler,
    )

    await view_details_handler(app)


async def view_plan_logic(app: "ReviewerApp") -> None:
    """Open the full plan.md in an external editor."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_previews import (
        view_plan_handler,
    )

    await view_plan_handler(app)


async def add_message_logic(app: "ReviewerApp") -> None:
    """Open the external editor to add/edit the user instruction message."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_previews import (
        add_message_handler,
    )

    await add_message_handler(app)


def toggle_all_logic(app: "ReviewerApp", plan: Any) -> None:
    """Toggle selection for all actions."""
    new_state = any(not action.selected for action in plan.actions)
    for action in plan.actions:
        action.selected = new_state

    from textual.widgets import Tree

    tree = app.query_one(Tree)

    # Recursively refresh all nodes that contain ActionData
    def refresh_recursive(node: Any):
        app._refresh_node(node)
        for child in node.children:
            refresh_recursive(child)

    refresh_recursive(tree.root)
