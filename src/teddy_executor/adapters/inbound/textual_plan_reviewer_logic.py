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
    from teddy_executor.core.domain.models.plan import ActionData
    from teddy_executor.core.domain.models.project_context import ContextItem


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
    from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
        handle_edit_action,
    )

    await handle_edit_action(app, node, action, _update_detail_view)


def refresh_node_logic(app: ReviewerApp, node: Any) -> None:
    """Refresh the label and state of a single tree node."""
    from teddy_executor.core.domain.models.plan import ActionData
    from teddy_executor.core.domain.models.project_context import ContextItem

    if isinstance(node.data, ActionData):
        node.label = format_node_label(node.data)
    elif isinstance(node.data, ContextItem):
        node.label = _format_context_item_label(node.data)


def _format_context_item_label(item: "ContextItem") -> str:
    """Format a context item label according to UI standards."""
    status_colors = {
        "M": "yellow",
        "??": "green",
        "A": "green",
        "D": "red",
        "U": "green",
    }
    clean_status = item.git_status.strip()
    # Map ?? to U for visual consistency
    display_status = "U" if clean_status == "??" else clean_status
    status_part = (
        f" [[{status_colors.get(clean_status, 'white')}]{display_status}[/]]"
        if clean_status
        else ""
    )

    token_str = f"{item.token_count / 1000.0:.1f}k"

    if not item.selected:
        return f"  [s dim]{item.path}{status_part} {token_str}[/]"

    return f"  [bold]{item.path}[/]{status_part} [#888888]{token_str}[/]"


def _build_context_section(app: ReviewerApp, tree: Any) -> Any:
    """Build the 'Context' tree section."""
    if not app.project_context:
        return None

    con_root = tree.root.add("[bold]Context[/]", data=CONTEXT_ROOT, expand=False)
    con_root.add_leaf("[#888888 italic]System:[/]", data=SYSTEM_LABEL)
    con_root.add_leaf(
        f"  [bold]{app.project_context.agent_name}[/]",
        data={
            "type": "SYSTEM_PROMPT",
            "agent": app.project_context.agent_name,
            "tokens": app.project_context.system_prompt_tokens,
        },
    )

    con_root.add_leaf("[#888888 italic]Session:[/]", data=SESSION_LABEL)
    for item in app.project_context.items:
        if item.scope == "Session":
            con_root.add_leaf(_format_context_item_label(item), data=item)

    con_root.add_leaf("[#888888 italic]Turn:[/]", data=TURN_LABEL)
    for item in app.project_context.items:
        if item.scope == "Turn":
            con_root.add_leaf(_format_context_item_label(item), data=item)

    return con_root


def on_mount_logic(app: Any) -> None:
    """Populate the action tree and set title when the app is mounted."""
    if getattr(app, "_tree_built", False) is True:
        return

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

    # 1. Context Section
    con_root = _build_context_section(app, tree)

    # 2. Rationale Section
    rat_root = tree.root.add("[bold]Rationale[/]", data=RATIONALE_ROOT, expand=True)

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

    # 3. Action Plan Section
    act_root = tree.root.add("[bold]Action Plan[/]", data=ACTION_PLAN_ROOT, expand=True)
    for action in app.plan.actions:
        if not hasattr(action, "_original_params"):
            action._original_params = action.params.copy()
        if action.type == "PRUNE" and not app.plan.is_session:
            continue
        act_root.add_leaf(format_node_label(action), data=action)

    # Initialize cursor: Context root if available, else Rationale root
    initial_node = con_root if con_root else rat_root

    tree.move_cursor(initial_node)
    tree.focus()
    app._tree_built = True
    app.call_after_refresh(_update_detail_view, app, initial_node.data)


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
