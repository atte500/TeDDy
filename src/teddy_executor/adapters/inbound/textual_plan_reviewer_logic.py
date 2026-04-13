from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, cast

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
        # Root node has no data usually, but our virtual roots do
        _update_detail_view(app, event.node.data)
    app.refresh_bindings()


def _update_detail_view(app: ReviewerApp, data: Any):
    """Populate the ParameterDetail view with action parameters, log, or rationale."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
        ParameterDetail,
        DetailItem,
    )
    from textual.widgets import Label, ListItem

    pane = app.query_one(ParameterDetail)
    pane.clear()

    if not data:
        pane.mount(ListItem(Label("Select an item to view details")))
        return

    if isinstance(data, dict) and data.get("type") == "RATIONALE_SECTION":
        # Don't repeat the section key for rationale sections
        pane.append(DetailItem("", data["content"]))
    elif data == "RATIONALE_ROOT":
        # Prevent race condition: don't update metadata if user has already moved cursor
        from textual.widgets import Tree

        tree = app.query_one(Tree)
        if tree.cursor_node and tree.cursor_node.data != "RATIONALE_ROOT":
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
    elif data == "ACTION_PLAN_ROOT":
        pane.mount(ListItem(Label("Select an action below to view details")))
    else:
        # data is likely ActionData
        from teddy_executor.core.domain.models.plan import ActionData

        if isinstance(data, ActionData):
            for key, val in resolve_action_parameters(data).items():
                pane.append(DetailItem(key, val))
        else:
            pane.mount(ListItem(Label("Select an item to view details")))


async def edit_action_logic(app: ReviewerApp, node: Any, action: ActionData) -> None:
    """Handles the (e)dit key logic by branching to modals or external editor."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
        handle_edit_action,
    )

    await handle_edit_action(app, node, action, _update_detail_view)


def refresh_node_logic(app: ReviewerApp, node: Any) -> None:
    """Refresh the label and state of a single tree node."""
    from teddy_executor.core.domain.models.plan import ActionData

    if isinstance(node.data, ActionData):
        node.label = format_node_label(node.data)


def on_mount_logic(app: Any) -> None:
    """Populate the action tree and set title when the app is mounted."""
    status_raw = (
        app.plan.metadata.get("Status") or app.plan.metadata.get("status") or ""
    )
    status_emoji = extract_status_emoji(status_raw)
    title_parts = [part for part in [status_emoji, app.plan.title] if part]
    app.title = " ".join(title_parts)

    from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
        ActionTree,
    )

    tree = app.query_one(ActionTree)
    tree.show_root = False
    tree.root.expand()

    # 1. Rationale Section
    rat_root = tree.root.add("[bold]Rationale[/]", data="RATIONALE_ROOT", expand=True)

    # Split on '### ' OR '1. ' (numeric lists at start of line)
    sections = re.split(r"\n(?=### |\d+\.\s+)", "\n" + app.plan.rationale)
    for section in sections:
        section = section.strip()
        if not section:
            continue
        lines = section.split("\n")
        # Strip markers (### or numeric prefix) from title, allowing for multiples
        title = re.sub(r"^(?:###\s*|\d+\.\s*)+", "", lines[0]).strip()
        content = "\n".join(lines[1:]).strip()
        rat_root.add_leaf(
            title,
            data={"type": "RATIONALE_SECTION", "title": title, "content": content},
        )

    # 2. Action Plan Section
    act_root = tree.root.add(
        "[bold]Action Plan[/]", data="ACTION_PLAN_ROOT", expand=True
    )
    for action in app.plan.actions:
        if not hasattr(action, "_original_params"):
            action._original_params = action.params.copy()
        if action.type == "PRUNE" and not app.plan.is_session:
            continue
        act_root.add_leaf(format_node_label(action), data=action)

    # Initialize with the Rationale root details highlighted
    tree.move_cursor(rat_root)
    tree.focus()
    app.call_after_refresh(_update_detail_view, app, "RATIONALE_ROOT")


def check_action_logic(app: ReviewerApp, action_name: str) -> bool:
    """Gate for enabling/disabling bindings based on state."""
    from textual.widgets import Tree
    from teddy_executor.core.domain.models.plan import ActionData

    tree = app.query_one(Tree)
    node = tree.cursor_node
    if not node or not isinstance(node.data, ActionData):
        return action_name not in (
            "execute_step",
            "edit_details",
            "revert",
            "view_details",
        )

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

    action: Any = node.data
    if isinstance(action, ActionData) and not action.executed:
        action.selected = not action.selected
        app._refresh_node(node)


async def on_list_view_selected_logic(app: ReviewerApp, item: Any) -> None:
    """Handle parameter editing when a DetailItem is selected in the right pane."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
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
    from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
        orchestrate_execution,
    )

    await orchestrate_execution(app, node, _update_detail_view)


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
