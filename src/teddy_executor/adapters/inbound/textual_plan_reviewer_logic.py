from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, cast

from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
    extract_status_emoji,
)
from teddy_executor.adapters.inbound.textual_plan_reviewer_execution import (
    resolve_action_parameters,
)
from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
    format_node_label,
)

if TYPE_CHECKING:
    from teddy_executor.adapters.inbound.textual_plan_reviewer_app import ReviewerApp


ALLOWED_RATIONALE_SECTIONS = [
    "Synthesis",
    "Justification",
    "Expectation",
    "State Dashboard",
]


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

    if __debug__ and app.ui_extension.handle_details(app, data, switcher):
        return

    if isinstance(data, dict) and data.get("type") == "RATIONALE_SECTION":
        switcher.current = "rationale-view"
        app.query_one("#rationale-content", Markdown).update(data["content"])
        return

    # Default to parameter view for everything else
    switcher.current = "params-view"
    pane = app.query_one(ParameterDetail)
    pane.clear()

    if not data:
        pane.mount(ListItem(Label("Select an item to view details")))
        return

    if data == "RATIONALE_ROOT":
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
                # Stringify Enum values for clean display
                val_str = val.value if hasattr(val, "value") else str(val)
                pane.append(DetailItem(key, val_str))
        else:
            pane.mount(ListItem(Label("Select an item to view details")))


async def edit_action_logic(app: ReviewerApp, node: Any, data: Any) -> None:
    """Handles the (e)dit key logic by branching to modals or external editor."""
    from teddy_executor.core.domain.models.plan import ActionData

    if __debug__ and app.ui_extension.handle_edit(app, data):
        return

    if isinstance(data, ActionData):
        from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
            handle_edit_action,
        )

        await handle_edit_action(app, node, data, _update_detail_view)


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

    # 0. Context Section (Restored root node with sibling-based indentation)
    if __debug__:
        from os import environ

        if environ.get("APP_ENV") == "prototype":
            app.ui_extension.extend_mount(app)
            con_root_list = [n for n in tree.root.children if n.data == "CONTEXT_ROOT"]
            con_root = con_root_list[0] if con_root_list else None

    # 1. Rationale Section
    rat_root = tree.root.add("[bold]Rationale[/]", data="RATIONALE_ROOT", expand=True)

    # Split on '### ' OR '1. ' (numeric lists at start of line)
    sections = re.split(r"\n(?=### |\d+\.\s+)", "\n" + app.plan.rationale)
    current_node = None
    for section in sections:
        section = section.strip()
        if not section:
            continue
        lines = section.split("\n")
        # Strip markers (### or numeric prefix) from title, allowing for multiples
        title = re.sub(r"^(?:###\s*|\d+\.\s*)+", "", lines[0]).strip()
        if title in ALLOWED_RATIONALE_SECTIONS:
            content = "\n".join(lines[1:]).strip()
            current_node = rat_root.add_leaf(
                title,
                data={"type": "RATIONALE_SECTION", "title": title, "content": content},
            )
        elif current_node:
            # Merge non-standard section into preceding standard node
            current_node.data["content"] += "\n\n" + section

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

    # Initialize with the Context details highlighted
    if __debug__:
        from os import environ

        if environ.get("APP_ENV") == "prototype":
            tree.move_cursor(con_root)
            tree.focus()
            app.call_after_refresh(_update_detail_view, app, "CONTEXT_ROOT")
            return

    tree.move_cursor(rat_root)
    tree.focus()
    app.call_after_refresh(_update_detail_view, app, "RATIONALE_ROOT")


def check_action_logic(app: ReviewerApp, action_name: str) -> bool:
    """Gate for enabling/disabling bindings based on state."""
    from textual.widgets import Tree
    from teddy_executor.core.domain.models.plan import ActionData

    tree = app.query_one(Tree)
    node = tree.cursor_node

    if __debug__:
        proto_result = app.ui_extension.handle_binding(app, action_name, node)
        if proto_result is not None:
            return proto_result

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

    if __debug__ and app.ui_extension.handle_selection(app, node):
        return

    if node.data in (
        "SESSION_LABEL",
        "TURN_LABEL",
        "CONTEXT_ROOT",
        "ACTION_PLAN_ROOT",
        "RATIONALE_ROOT",
    ):
        return

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
    from textual.widgets import Tree
    from teddy_executor.core.domain.models.plan import ActionData

    tree = app.query_one(Tree)

    # 1. Determine new state based on actions
    new_state = any(not action.selected for action in plan.actions)

    # 2. Update Actions
    for action in plan.actions:
        action.selected = new_state

    # 3. Recursively refresh nodes and update Context nodes
    def refresh_recursive(node: Any):
        if __debug__ and app.ui_extension.handle_toggle_all(app, node, new_state):
            pass

        if isinstance(node.data, ActionData):
            app._refresh_node(node)

        for child in node.children:
            refresh_recursive(child)

    refresh_recursive(tree.root)
