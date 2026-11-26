from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, cast

from teddy_executor.adapters.inbound.textual_plan_reviewer_execution import (
    resolve_action_parameters,
)
from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
    format_node_label,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from teddy_executor.adapters.inbound.textual_plan_reviewer_app import ReviewerApp
    from teddy_executor.core.domain.models.plan import ActionData


# Label for content the author left untitled: text before the first heading,
# and a rationale that carries no heading at all.
RATIONALE_FALLBACK_TITLE = "Untitled"

# Tree Node Identifiers
CONTEXT_ROOT = "CONTEXT_ROOT"
SYSTEM_LABEL = "SYSTEM_LABEL"
SESSION_LABEL = "SESSION_LABEL"
TURN_LABEL = "TURN_LABEL"
HISTORY_LABEL = "HISTORY_LABEL"
RATIONALE_ROOT = "RATIONALE_ROOT"
ACTION_PLAN_ROOT = "ACTION_PLAN_ROOT"

# Every payload that marks a tree node as a navigation section. Derived from the
# identifiers above, so a new section cannot be introduced without joining the
# navigation walk.
SECTION_SENTINELS = frozenset(
    {
        CONTEXT_ROOT,
        SYSTEM_LABEL,
        SESSION_LABEL,
        TURN_LABEL,
        HISTORY_LABEL,
        RATIONALE_ROOT,
        ACTION_PLAN_ROOT,
    }
)


def is_section_payload(data: Any) -> bool:
    """Report whether a node payload identifies a navigation section.

    File rows carry an unhashable ``ContextItem`` and the agent row carries a
    dict, so the membership test is gated on ``str`` instead of trusting the
    payload's type.
    """
    return isinstance(data, str) and data in SECTION_SENTINELS


# Summary logic moved to textual_plan_reviewer_helpers.py


_FENCE_PATTERN = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})")
_HEADING_PREFIX = "### "


def _trim_blank_lines(lines: list[str]) -> str:
    """Joins ``lines`` with the blank lines around them removed, not inside."""
    start = 0
    end = len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return "\n".join(lines[start:end])


def _opening_fence(line: str) -> str | None:
    """Returns the fence sequence opening a block on ``line``, or ``None``."""
    match = _FENCE_PATTERN.match(line)
    return match.group("fence") if match else None


def _closes_fence(line: str, fence: str) -> bool:
    """Returns whether ``line`` closes a block opened by ``fence``.

    A closer carries the opener's character and at least its length, so a
    three-backtick line inside a four-backtick block stays content.
    """
    stripped = line.strip()
    return len(stripped) >= len(fence) and stripped == fence[0] * len(stripped)


def rationale_sections(rationale: str) -> list[tuple[str, str]]:
    """Splits a rationale into one section per authored `###` heading.

    Every `### ` heading at the start of a line opens a section whatever its
    title, so a plan that adds, renames, or reorders a section stays reviewable
    in the authored order. Fenced blocks are scanned so a `### ` line inside one
    stays body text: an opening fence of three or more backticks or tildes is
    closed only by the same character at or above the same length, and an
    unclosed fence keeps the rest of the rationale in its own section instead of
    tearing the block in two. Text before the first heading becomes a leading
    ``RATIONALE_FALLBACK_TITLE`` section, and a rationale with no heading at all
    becomes a single such section. Only the blank lines around a body are
    trimmed, so an indented line stays body content and a blank rationale yields
    no sections.
    """
    sections: list[tuple[str, str]] = []
    title: str | None = None
    body: list[str] = []
    fence: str | None = None

    def flush() -> None:
        nonlocal body
        content = _trim_blank_lines(body)
        if title is not None:
            sections.append((title, content))
        elif content:
            sections.append((RATIONALE_FALLBACK_TITLE, content))
        body = []

    for line in rationale.splitlines():
        if fence is not None:
            if _closes_fence(line, fence):
                fence = None
            body.append(line)
            continue
        opening = _opening_fence(line)
        if opening is not None:
            fence = opening
            body.append(line)
            continue
        if line.startswith(_HEADING_PREFIX):
            flush()
            title = line.removeprefix(_HEADING_PREFIX).strip()
            continue
        body.append(line)

    flush()
    return sections


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
    )
    from textual.widgets import ContentSwitcher

    try:
        switcher = app.query_one(ContentSwitcher)
        pane = app.query_one(ParameterDetail)
    except Exception:
        return

    if not pane.is_attached:
        return

    rationale = _rationale_content(data)
    if _is_context_data(data):
        _update_context_detail(app, switcher, pane, data)
    elif rationale is not None:
        _update_rationale_detail(app, switcher, rationale)
    else:
        _update_action_detail(app, switcher, pane, data)


def _is_context_data(data: Any) -> bool:
    """Check if data belongs to the context section."""
    from teddy_executor.core.domain.models.project_context import ContextItem

    return (
        data in (CONTEXT_ROOT, SYSTEM_LABEL, SESSION_LABEL, TURN_LABEL, HISTORY_LABEL)
        or isinstance(data, ContextItem)
        or (isinstance(data, dict) and data.get("type") == "SYSTEM_PROMPT")
    )


def _rationale_content(data: Any) -> str | None:
    """Returns the rationale Markdown a section node renders, or ``None``.

    The whole-block fallback is itself a section node, so every node that
    carries rationale content uses the same dict shape.
    """
    if isinstance(data, dict) and data.get("type") == "RATIONALE_SECTION":
        return str(data["content"])
    return None


def _update_context_detail(app: ReviewerApp, switcher: Any, pane: Any, data: Any):
    """Render details for context items or aggregates."""
    switcher.current = "params-view"
    pane.clear()
    from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
        populate_context_detail,
    )

    populate_context_detail(app, pane, data)


def _update_rationale_detail(app: ReviewerApp, switcher: Any, content: str):
    """Render rationale Markdown in the detail pane."""
    from textual.widgets import Markdown

    switcher.current = "rationale-view"
    app.query_one("#rationale-content", Markdown).update(content)


def _update_action_detail(app: ReviewerApp, switcher: Any, pane: Any, data: Any):
    """Render details for action plan roots or individual actions."""
    from textual.widgets import Label, ListItem

    switcher.current = "params-view"
    pane.clear()

    if not data:
        pane.mount(ListItem(Label("Select an item to view details")))
        return

    if data == RATIONALE_ROOT:
        _render_rationale_root_detail(app, pane)
    elif data == ACTION_PLAN_ROOT:
        pane.mount(ListItem(Label("Select an action below to view details")))
    else:
        _render_action_data_detail(pane, data)


def _render_rationale_root_detail(app: ReviewerApp, pane: Any):
    """Render metadata for the Rationale root node."""
    from textual.widgets import Tree
    from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import DetailItem

    tree = app.query_one(Tree)
    if tree.cursor_node and tree.cursor_node.data != RATIONALE_ROOT:
        return

    # Fallback to project_context for agent identity
    agent = (
        app.plan.metadata.get("Agent")
        or app.plan.metadata.get("agent")
        or (app.project_context.agent_name if app.project_context else "Unknown")
    )
    plan_type = (
        app.plan.metadata.get("Plan Type")
        or app.plan.metadata.get("plan_type")
        or "Development"
    )
    status = app.plan.metadata.get("Status") or app.plan.metadata.get("status") or "N/A"
    pane.append(DetailItem("Agent", agent))
    pane.append(DetailItem("Plan Type", plan_type))
    pane.append(DetailItem("Status", status))


def _render_action_data_detail(pane: Any, data: Any):
    """Render parameters for an ActionData object."""
    from teddy_executor.core.domain.models.plan import ActionData
    from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import DetailItem
    from textual.widgets import Label, ListItem

    if isinstance(data, ActionData):
        for key, val in resolve_action_parameters(data).items():
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
        session_root = app.project_context.session_root if app.project_context else None
        node.label = format_context_item_label(node.data, session_root)


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
        "focus_next",
        "focus_prev",
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
        # Always refresh detail view based on CURRENT highlighting
        # This ensures totals update if the root is selected but a child is toggled
        from textual.widgets import Tree

        tree = app.query_one(Tree)
        if tree.cursor_node:
            _update_detail_view(app, tree.cursor_node.data)


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
