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

# A parameter value above this budget, or carrying any newline, has no honest
# single-line representation and opens in the external editor instead.
MAX_INLINE_PARAM_LENGTH = 100

# The persona leaf beneath the System row: its payload type and the one
# formatter both mount time and a persona switch render through, so a switch
# cannot leave the label shaped differently from how the tree was built.
SYSTEM_PROMPT_LEAF_TYPE = "SYSTEM_PROMPT"


def format_system_prompt_label(agent_name: str, tokens: int) -> str:
    """Render the persona leaf's label: the agent name and its token budget."""
    return f"  [bold]{agent_name}[/] [#888888]{tokens / 1000.0:.1f}k[/]"


def needs_external_editor(value: str) -> bool:
    """Whether a rendered parameter value must open in the external editor.

    A value carrying a newline loses its line breaks in a single-line `Input`,
    and one above the inline budget degrades into horizontal scrolling. The
    budget triggers only strictly above itself, so a value at exactly
    ``MAX_INLINE_PARAM_LENGTH`` stays inline.
    """
    return "\n" in value or len(value) > MAX_INLINE_PARAM_LENGTH


def extract_status_emoji(raw_status: str) -> str:
    """Extracts the status emoji, preferring anchored status lines."""
    # Priority 1: Anchored status line (matches SessionPruningService logic)
    anchored_match = re.search(
        r"^- \*\*Status:\*\*.*([🟢🟡🔴])", raw_status, re.MULTILINE
    )
    if anchored_match:
        return anchored_match.group(1)

    # Priority 2: Fallback to first occurring emoji (resilience for unanchored strings)
    emojis = re.findall(r"[🟢🟡🔴]", raw_status)
    return emojis[0] if emojis else ""


def populate_context_detail(app: "ReviewerApp", pane: Any, data: Any) -> None:
    """Extract context-specific detail population logic."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import DetailItem
    from teddy_executor.core.domain.models.project_context import ContextItem
    from teddy_executor.core.utils.markdown import is_session_history_path
    from teddy_executor.core.utils.model_identity import split_model_identity
    from teddy_executor.core.utils.money import format_cost_usd

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
    elif isinstance(data, dict) and data.get("type") == SYSTEM_PROMPT_LEAF_TYPE:
        pane.append(DetailItem("Agent", data.get("agent", "Unknown")))
        pane.append(DetailItem("Tokens", f"{data.get('tokens', 0) / 1000.0:.1f}k"))
    elif app.project_context:
        # Context Aggregate View - Only sum SELECTED items
        selected_items = [i for i in app.project_context.items if i.selected]
        selected_file_tokens = sum(i.token_count for i in selected_items)
        system_info_tokens = app.project_context.content_tokens - selected_file_tokens
        total_tokens = (
            app.project_context.content_tokens
            + app.project_context.system_prompt_tokens
        )
        window_val = (
            f"{app.project_context.total_window / 1000.0:.0f}k"
            if app.project_context.total_window > 0
            else "???"
        )
        pane.append(
            DetailItem(
                "Total Context",
                f"{total_tokens / 1000.0:.1f}k / {window_val} tokens",
            )
        )
        pane.append(
            DetailItem(
                "• System",
                f"{(app.project_context.system_prompt_tokens + system_info_tokens) / 1000.0:.1f}k",
            )
        )
        session_root = app.project_context.session_root
        session_tokens = sum(
            i.token_count
            for i in selected_items
            if i.scope == "Session"
            and not is_session_history_path(i.path, session_root)
        )
        turn_tokens = sum(
            i.token_count
            for i in selected_items
            if i.scope == "Turn" and not is_session_history_path(i.path, session_root)
        )
        history_tokens = sum(
            i.token_count
            for i in selected_items
            if is_session_history_path(i.path, session_root)
        )

        pane.append(DetailItem("• Session", f"{session_tokens / 1000.0:.1f}k"))
        pane.append(DetailItem("• Turn", f"{turn_tokens / 1000.0:.1f}k"))
        pane.append(DetailItem("• History", f"{history_tokens / 1000.0:.1f}k"))

        model_name, provider = split_model_identity(app.project_context.model_name)
        pane.append(DetailItem("Model", model_name))
        pane.append(DetailItem("Provider", provider))
        pane.append(
            DetailItem(
                "Session Cost", format_cost_usd(app.project_context.session_cost)
            )
        )


# Editor helpers moved to textual_plan_reviewer_editor.py


def format_context_item_label(
    item: "ContextItem", session_root: str | None = None
) -> str:
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

    from teddy_executor.core.utils.markdown import get_session_history_display_name

    disp_name = get_session_history_display_name(item.path, session_root)
    display_path = disp_name if disp_name else item.path

    if not item.selected:
        return f"  [s dim]{display_path}{status_part} {token_str}[/]"
    return f"  [bold]{display_path}[/]{status_part} [#888888]{token_str}[/]"


def build_context_section(app: "ReviewerApp", tree: Any) -> Any:
    """Build the 'Context' tree section."""
    if not app.project_context:
        return None
    from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
        CONTEXT_ROOT,
        SYSTEM_LABEL,
        SESSION_LABEL,
        TURN_LABEL,
        HISTORY_LABEL,
    )
    from teddy_executor.core.utils.markdown import (
        is_own_session_path,
        is_session_history_path,
        get_session_history_sort_key,
    )

    session_root = app.project_context.session_root
    con_root = tree.root.add("[bold]Context[/]", data=CONTEXT_ROOT, expand=False)
    con_root.add_leaf("[#888888 italic]System:[/]", data=SYSTEM_LABEL)
    con_root.add_leaf(
        format_system_prompt_label(
            app.project_context.agent_name,
            app.project_context.system_prompt_tokens,
        ),
        data={
            "type": SYSTEM_PROMPT_LEAF_TYPE,
            "agent": app.project_context.agent_name,
            "tokens": app.project_context.system_prompt_tokens,
        },
    )

    # Standard context items grouped by scope
    for scope, label in [("Session", SESSION_LABEL), ("Turn", TURN_LABEL)]:
        con_root.add_leaf(f"[#888888 italic]{scope}:[/]", data=label)
        count = 0
        for item in app.project_context.items:
            if item.scope == scope and not is_own_session_path(item.path, session_root):
                con_root.add_leaf(
                    format_context_item_label(item, session_root), data=item
                )
                count += 1
        if count == 0:
            con_root.add_leaf("  [#888888](None)[/]", data=label)

    # Chronological history turns
    history_items = [
        item
        for item in app.project_context.items
        if is_session_history_path(item.path, session_root)
    ]
    if history_items:
        con_root.add_leaf("[#888888 italic]History:[/]", data=HISTORY_LABEL)
        history_items.sort(key=lambda x: get_session_history_sort_key(x.path))
        for item in history_items:
            con_root.add_leaf(format_context_item_label(item, session_root), data=item)

    return con_root


def _preorder(root: Any) -> Any:
    """Yield ``root`` and every descendant in render order."""
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.children))


def section_sequence(tree: Any) -> list[Any]:
    """Return the built tree's section nodes in render order.

    The sequence is read from the tree rather than from a constant list, so a
    panel that carries no context root and a session with no history both walk
    exactly the sections that exist. An empty scope group renders a ``(None)``
    leaf repeating its header's own sentinel, so each section is recorded once:
    keeping the first occurrence leaves the cursor on the header instead of a
    placeholder row.
    """
    from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
        is_section_payload,
    )

    sequence: list[Any] = []
    seen: set[str] = set()
    for node in _preorder(tree.root):
        data = node.data
        if is_section_payload(data) and data not in seen:
            seen.add(data)
            sequence.append(node)
    return sequence


def containing_section(node: Any) -> Any:
    """Return the section node governing ``node``, or ``None``.

    Membership is positional, not parental: the context pane renders each scope
    header and its rows as siblings under the Context root, so a row is governed
    by the last section node at or before it in render order. A section node
    governs itself, and the invisible tree root governs nothing.
    """
    from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
        is_section_payload,
    )

    root = node
    while root.parent is not None:
        root = root.parent

    governing = None
    for current in _preorder(root):
        if is_section_payload(current.data):
            governing = current
        if current is node:
            return governing
    return None


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
        RATIONALE_FALLBACK_TITLE,
        rationale_sections,
    )

    rat_root = tree.root.add("[bold]Rationale[/]", data=RATIONALE_ROOT, expand=True)
    for title, content in rationale_sections(app.plan.rationale):
        label = title
        if title == RATIONALE_FALLBACK_TITLE:
            # Untitled content is secondary: keep it visually quieter so it
            # does not read as one of the authored sections.
            label = f"[#888888 italic]{title}[/]"
        rat_root.add_leaf(
            label,
            data={"type": "RATIONALE_SECTION", "title": title, "content": content},
        )

    # 3. Action Plan Section
    act_root = tree.root.add("[bold]Action Plan[/]", data=ACTION_PLAN_ROOT, expand=True)
    for action in app.plan.actions:
        if not hasattr(action, "_original_params"):
            action._original_params = action.params.copy()
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
        if action.type == "MOVE":
            source = params.get("source", "")
            destination = params.get("destination", "")
            summary = f"{source} -> {destination}"
        else:
            summary = str(
                params.get("path")
                or params.get("resource")
                or params.get("command", "")
            )

    if len(summary) > MAX_LABEL_LENGTH:
        summary = summary[: MAX_LABEL_LENGTH - 3] + "..."
    return summary


# Parameters a reviewer edits as text while the run consumes them as booleans.
# The parser owns the one truthiness rule, so an edited "false" cannot survive
# as the truthy string it looks like.
BOOLEAN_PARAM_KEYS = frozenset(
    {"overwrite", "match_all", "allow_failure", "background", "recursive"}
)


def _apply_param_edit(action: Any, key: str, new_val: str) -> None:
    """Helper to apply parameter edits back to the action."""
    list_keys = {"queries", "reference_files"}
    if key in list_keys:
        action.params[key] = [v.strip() for v in str(new_val).split(",") if v.strip()]
    elif key in BOOLEAN_PARAM_KEYS:
        from teddy_executor.core.services.parser_infrastructure import coerce_param

        action.params[key] = coerce_param(new_val, bool)
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

        ptf = getattr(action, "pending_temp_file", None)
        if isinstance(ptf, str):
            app._system_env.delete_file(ptf)
        action.pending_temp_file = None

        app._refresh_node(node)
        update_fn(app, action)
        app.refresh_bindings()
