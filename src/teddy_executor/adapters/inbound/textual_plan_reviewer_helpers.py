from __future__ import annotations
import logging
import re
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from teddy_executor.adapters.inbound.textual_plan_reviewer_app import ReviewerApp
    from teddy_executor.core.domain.models.plan import ActionData
    from teddy_executor.core.domain.models.project_context import ContextItem

logger = logging.getLogger(__name__)

MAX_LABEL_LENGTH = 60


def extract_status_emoji(raw_status: str) -> str:
    """Extracts the last emoji from a status string."""
    emojis = re.findall(r"[🟢🟡🔴]", raw_status)
    return emojis[-1] if emojis else ""


def populate_context_detail(app: "ReviewerApp", pane: Any, data: Any) -> None:
    """Extract context-specific detail population logic."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import DetailItem
    from teddy_executor.core.domain.models.project_context import ContextItem

    if isinstance(data, ContextItem):
        pane.append(DetailItem("Path", data.path))
        pane.append(DetailItem("Tokens", f"{data.token_count / 1000.0:.1f}k"))
        status_map = {
            "M": "Modified",
            "??": "Untracked",
            "U": "Untracked",
            "A": "Added",
            "D": "Deleted",
        }
        status_text = status_map.get(data.git_status.strip(), "Unmodified")
        pane.append(DetailItem("Git Status", status_text))
        pane.append(DetailItem("Scope", data.scope))
        if data.auto_prune_reason:
            pane.append(DetailItem("Auto-Prune", data.auto_prune_reason))
    elif isinstance(data, dict) and data.get("type") == "SYSTEM_PROMPT":
        pane.append(DetailItem("Agent", data.get("agent", "Unknown")))
        pane.append(DetailItem("Tokens", f"{data.get('tokens', 0) / 1000.0:.1f}k"))
    elif app.project_context:
        # Context Aggregate View - Only sum SELECTED items
        selected_items = [i for i in app.project_context.items if i.selected]
        total_tokens = (
            sum(i.token_count for i in selected_items)
            + app.project_context.system_prompt_tokens
        )
        pane.append(
            DetailItem(
                "Total Context",
                f"{total_tokens / 1000.0:.1f}k / {app.project_context.total_window / 1000.0:.0f}k tokens",
            )
        )
        pane.append(
            DetailItem(
                "• System", f"{app.project_context.system_prompt_tokens / 1000.0:.1f}k"
            )
        )
        pane.append(
            DetailItem(
                "• Session",
                f"{sum(i.token_count for i in selected_items if i.scope == 'Session') / 1000.0:.1f}k",
            )
        )
        pane.append(
            DetailItem(
                "• Turn",
                f"{sum(i.token_count for i in selected_items if i.scope == 'Turn') / 1000.0:.1f}k",
            )
        )


# Editor helpers moved to textual_plan_reviewer_editor.py


def format_context_item_label(item: "ContextItem") -> str:
    """Format a context item label according to UI standards."""
    status_colors = {
        "M": "yellow",
        "??": "green",
        "A": "green",
        "D": "red",
        "U": "green",
    }
    clean_status = item.git_status.strip()
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


def build_context_section(app: "ReviewerApp", tree: Any) -> Any:
    """Build the 'Context' tree section."""
    if not app.project_context:
        return None
    from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
        CONTEXT_ROOT,
        SYSTEM_LABEL,
        SESSION_LABEL,
        TURN_LABEL,
    )

    con_root = tree.root.add("[bold]Context[/]", data=CONTEXT_ROOT, expand=False)
    con_root.add_leaf("[#888888 italic]System:[/]", data=SYSTEM_LABEL)
    token_str = f" [#888888]{app.project_context.system_prompt_tokens / 1000.0:.1f}k[/]"
    con_root.add_leaf(
        f"  [bold]{app.project_context.agent_name}[/]{token_str}",
        data={
            "type": "SYSTEM_PROMPT",
            "agent": app.project_context.agent_name,
            "tokens": app.project_context.system_prompt_tokens,
        },
    )
    con_root.add_leaf("[#888888 italic]Session:[/]", data=SESSION_LABEL)
    session_count = 0
    for item in app.project_context.items:
        if item.scope == "Session":
            con_root.add_leaf(format_context_item_label(item), data=item)
            session_count += 1
    if session_count == 0:
        con_root.add_leaf("  [#888888](None)[/]", data=SESSION_LABEL)

    con_root.add_leaf("[#888888 italic]Turn:[/]", data=TURN_LABEL)
    turn_count = 0
    for item in app.project_context.items:
        if item.scope == "Turn":
            con_root.add_leaf(format_context_item_label(item), data=item)
            turn_count += 1
    if turn_count == 0:
        con_root.add_leaf("  [#888888](None)[/]", data=TURN_LABEL)

    return con_root


def handle_mount_logic(app: Any, update_detail_fn: Any) -> None:
    """Populate the action tree and set title when the app is mounted."""
    if getattr(app, "_tree_built", False) is True:
        return

    status_raw = (
        app.plan.metadata.get("Status") or app.plan.metadata.get("status") or ""
    )
    status_emoji = extract_status_emoji(status_raw)
    title_parts = [part for part in [status_emoji, app.plan.title] if part]
    app.title = " ".join(title_parts)

    from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import ActionTree

    tree = app.query_one(ActionTree)
    tree.show_root = False
    tree.root.expand()

    # 1. Context Section
    con_root = build_context_section(app, tree)

    # 2. Rationale Section
    from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
        RATIONALE_ROOT,
        ACTION_PLAN_ROOT,
        ALLOWED_RATIONALE_SECTIONS,
    )

    rat_root = tree.root.add("[bold]Rationale[/]", data=RATIONALE_ROOT, expand=True)

    # Split on '### ' OR '1. ' (numeric lists at start of line)
    sections = re.split(r"\n(?=### |\d+\.\s+)", "\n" + app.plan.rationale)
    current_node = None
    for section in sections:
        section = section.strip()
        if not section:
            continue
        lines = section.split("\n")
        title = re.sub(r"^(?:###\s*|\d+\.\s*)+", "", lines[0]).strip()
        if title in ALLOWED_RATIONALE_SECTIONS:
            content = "\n".join(lines[1:]).strip()
            current_node = rat_root.add_leaf(
                title,
                data={"type": "RATIONALE_SECTION", "title": title, "content": content},
            )
        elif current_node:
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
    app.call_after_refresh(update_detail_fn, app, initial_node.data)


def format_node_label(action: "ActionData") -> str:
    """Format the label for a tree node based on action state."""
    from teddy_executor.core.domain.models.plan import ExecutionStatus

    summary = get_action_summary(action)
    # Ensure Enum types are stringified (e.g. ActionType.CREATE -> "CREATE")
    type_str = action.type.value if hasattr(action.type, "value") else str(action.type)

    if action.state == ExecutionStatus.RUNNING:
        return f"[blue][RUNNING] {type_str}: {summary}[/]"

    if action.executed:
        color = "green" if action.state.value == "SUCCESS" else "red"
        return f"[{color}][{action.state.value}] {type_str}: {summary}[/]"

    prefix = "[✓]" if action.selected else "[ ]"
    label = f"{prefix} {type_str}: {summary}"
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


def _apply_param_edit(action: Any, key: str, new_val: str) -> None:
    """Helper to apply parameter edits back to the action."""
    if action.type == "PROMPT" and key == "response":
        action.user_response = str(new_val)
        return
    list_keys = {"queries", "reference_files"}
    if key in list_keys:
        action.params[key] = [v.strip() for v in str(new_val).split(",") if v.strip()]
    else:
        action.params[key] = str(new_val)


def handle_revert(app: ReviewerApp, node: Any, update_fn: Any) -> None:
    """Revert manual modifications for the currently highlighted action."""
    action: Optional[ActionData] = node.data
    if action and action.modified:
        action.modified = False
        action.modified_fields.clear()
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
