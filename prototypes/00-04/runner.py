import sys
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Optional, List, Dict
from unittest.mock import MagicMock

# Ensure project root is in sys.path for imports
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import textual.widgets as widgets
from textual.app import ComposeResult
from textual.widgets import Tree, Label, ListItem, Markdown, ContentSwitcher

from teddy_executor.adapters.inbound.textual_plan_reviewer_app import ReviewerApp
from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
    ActionTree, ParameterDetail, DetailItem
)
import teddy_executor.adapters.inbound.textual_plan_reviewer_logic as reviewer_logic
from teddy_executor.core.domain.models.plan import Plan, ActionData, ActionType

# --- Prototype DTOs ---

@dataclass
class ContextFileData:
    path: str
    tokens: int
    git_status: str  # e.g. "M", "??", ""
    scope: str       # "Session" or "Turn"
    selected: bool = True
    auto_prune_reason: Optional[str] = None

    def format_label(self) -> str:
        status_colors = {"M": "yellow", "??": "green", "A": "green", "D": "red"}
        clean_status = self.git_status.strip()
        display_status = "U" if clean_status == "??" else clean_status
        status_part = f" [[{status_colors.get(clean_status, 'white')}]{display_status}[/]]" if clean_status else ""
        
        token_str = f"{self.tokens / 1000.0:.1f}k"
        
        if not self.selected:
            # Strikethrough and dimmed for pruned items
            # Images show the path and status are struck through, tokens are struck through
            return f"  [s dim]{self.path}{status_part} {token_str}[/]"
        
        # Base label logic: bold path, colored bracketed status, gray tokens
        return f"  [bold]{self.path}[/]{status_part} [#888888]{token_str}[/]"

@dataclass
class SystemPromptData:
    agent: str
    tokens: int
    path: str = ".teddy/prompts/architect.xml"

# --- Logging Setup for verification ---
import logging
logging.basicConfig(
    filename=str(Path(__file__).parent / "prototype.log"),
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'
)
logger = logging.getLogger("Prototype")

# --- Monkey-Patching Logic ---

# We don't call the originals to avoid duplication or interfering with state
original_on_mount = reviewer_logic.on_mount_logic
original_update_detail = reviewer_logic._update_detail_view
original_check_action = reviewer_logic.check_action_logic
original_toggle_selection = reviewer_logic.toggle_selection_logic
original_toggle_all = reviewer_logic.toggle_all_logic

CONTEXT_ROOT = "CONTEXT_ROOT"
SYSTEM_LABEL = "SYSTEM_LABEL"
SESSION_LABEL = "SESSION_LABEL"
TURN_LABEL = "TURN_LABEL"

def rebuild_prototype_tree(app: Any) -> None:
    """Guarded override of tree construction."""
    if getattr(app, "_prototype_built", False):
        logger.debug(f"[BUILD] Skipping duplicate build for app: {id(app)}")
        return

    import re
    from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
        extract_status_emoji, format_node_label
    )
    logger.debug(f"[BUILD] Building tree for the first time for app: {id(app)}")

    # 1. Set Title
    status_raw = app.plan.metadata.get("Status", "N/A")
    status_emoji = extract_status_emoji(status_raw)
    app.title = f"{status_emoji} {app.plan.title}".strip()

    tree = app.query_one(ActionTree)
    tree.clear() # Clean slate
    tree.show_root = False
    tree.root.expand()

    # 2. Add Context Section (Collapsed by default)
    con_root = tree.root.add("[bold]Context[/]", data=CONTEXT_ROOT, expand=False)

    # Hierarchy matching images: Italic headers, indented bold files
    con_root.add_leaf("[#888888 italic]System:[/]", data=SYSTEM_LABEL)
    con_root.add_leaf(f"  [bold]Architect[/]", data=SystemPromptData("Architect", 2500))

    con_root.add_leaf("[#888888 italic]Session:[/]", data=SESSION_LABEL)
    sim_data = [
        ContextFileData("src/core.py", 1200, "", "Session", True),
        ContextFileData("src/utils.py", 450, "M", "Session", True),
        ContextFileData("docs/plan-INVALID.md", 300, "??", "Turn", False, "Failed plan validation"),
        ContextFileData("reports/turn-01-FAILURE.md", 1500, "", "Turn", False, "Non-green plan"),
        ContextFileData("src/heavy_logic.py", 15000, "M", "Turn", False, "Exceeds 15k token limit"),
    ]

    turn_header_added = False
    for item in sim_data:
        if item.scope == "Turn" and not turn_header_added:
            con_root.add_leaf("[#888888 italic]Turn:[/]", data=TURN_LABEL)
            turn_header_added = True
        con_root.add_leaf(item.format_label(), data=item)

    # 3. Add Rationale Section
    rat_root = tree.root.add("[bold]Rationale[/]", data="RATIONALE_ROOT", expand=True)
    sections = re.split(r"\n(?=### |\d+\.\s+)", "\n" + app.plan.rationale)
    for section in sections:
        section = section.strip()
        if not section: continue
        title = re.sub(r"^(?:###\s*|\d+\.\s*)+", "", section.split("\n")[0]).strip()
        if title in reviewer_logic.ALLOWED_RATIONALE_SECTIONS:
            content = "\n".join(section.split("\n")[1:]).strip()
            rat_root.add_leaf(title, data={"type": "RATIONALE_SECTION", "title": title, "content": content})

    # 4. Add Action Plan Section
    act_root = tree.root.add("[bold]Action Plan[/]", data="ACTION_PLAN_ROOT", expand=True)
    for action in app.plan.actions:
        act_root.add_leaf(format_node_label(action), data=action)

    # 5. Initialize Cursor at Context Root
    tree.move_cursor(con_root)
    tree.focus()
    app._prototype_built = True
    app.call_after_refresh(patched_update_detail_view, app, CONTEXT_ROOT)

def patched_update_detail_view(app: Any, data: Any):
    from textual.widgets import ContentSwitcher, Markdown
    switcher = app.query_one(ContentSwitcher)
    pane = app.query_one(ParameterDetail)
    logger.debug(f"Updating detail view for data: {data}")

    if data in (CONTEXT_ROOT, SYSTEM_LABEL, SESSION_LABEL, TURN_LABEL) or isinstance(data, (ContextFileData, SystemPromptData)):
        switcher.current = "params-view"
        pane.clear()

        if isinstance(data, ContextFileData):
            pane.append(DetailItem("Path", data.path))
            pane.append(DetailItem("Tokens", f"{data.tokens / 1000.0:.1f}k"))
            status_map = {"M": "Modified", "??": "Untracked", "U": "Untracked", "A": "Added", "D": "Deleted"}
            status_text = status_map.get(data.git_status.strip(), "Unmodified")
            pane.append(DetailItem("Git Status", status_text))
            pane.append(DetailItem("Scope", data.scope))
            if data.auto_prune_reason:
                pane.append(DetailItem("Auto-Prune", data.auto_prune_reason))
        elif isinstance(data, SystemPromptData):
            pane.append(DetailItem("Agent", data.agent))
            pane.append(DetailItem("Path", data.path))
            pane.append(DetailItem("Tokens", f"{data.tokens / 1000.0:.1f}k"))
        else:
            # Context Aggregate View (Matched to Image)
            session_k, turn_k, prompt_k = 1.9, 16.5, 2.5
            total_k = session_k + turn_k + prompt_k
            pane.append(DetailItem("Total Context", f"{total_k:.1f}k / 128k tokens"))
            pane.append(DetailItem("• System", f"{prompt_k:.1f}k"))
            pane.append(DetailItem("• Session", f"{session_k:.1f}k"))
            pane.append(DetailItem("• Turn", f"{turn_k:.1f}k"))
        return

    # Handle rationale sections explicitly
    if isinstance(data, dict) and data.get("type") == "RATIONALE_SECTION":
        switcher.current = "rationale-view"
        app.query_one("#rationale-content", Markdown).update(data["content"])
        return

    # Fallback for original roots
    switcher.current = "params-view"
    pane.clear()
    if data == "RATIONALE_ROOT":
        pane.append(DetailItem("Agent", "Unknown"))
        pane.append(DetailItem("Plan Type", "Development"))
        pane.append(DetailItem("Status", "N/A"))
    elif data == "ACTION_PLAN_ROOT":
        from textual.widgets import Label
        pane.mount(ListItem(Label("Select an action below to view details")))
    else:
        # Action Data
        original_update_detail(app, data)

def patched_check_action_logic(app: Any, action_name: str) -> bool:
    tree = app.query_one(ActionTree)
    node = tree.cursor_node
    if node and (node.data in (CONTEXT_ROOT, SYSTEM_LABEL, SESSION_LABEL, TURN_LABEL) or isinstance(node.data, (ContextFileData, SystemPromptData))):
        # Add 'edit_details' (e) as seen in images
        return action_name in ("edit_details", "focus_right", "focus_left", "jump_next", "jump_prev", "cancel")
    return original_check_action(app, action_name)

def patched_toggle_selection_logic(app: Any, node: Any) -> None:
    if isinstance(node.data, ContextFileData):
        node.data.selected = not node.data.selected
        node.label = node.data.format_label()
        return
    if node.data in (CONTEXT_ROOT, SYSTEM_LABEL, SESSION_LABEL, TURN_LABEL):
        return
    original_toggle_selection(app, node)

def patched_toggle_all_logic(app: Any, plan: Any) -> None:
    original_toggle_all(app, plan)
    # Also toggle all context files
    tree = app.query_one(ActionTree)
    new_state = any(not a.selected for action in plan.actions) # Simplified logic for proto
    def refresh_recursive(node: Any):
        if isinstance(node.data, ContextFileData):
            node.data.selected = new_state
            node.label = node.data.format_label()
        for child in node.children:
            refresh_recursive(child)
    refresh_recursive(tree.root)

# --- Total Override Patching ---
import teddy_executor.adapters.inbound.textual_plan_reviewer_app as app_mod

# 1. Patch the logic module used by both app and methods
reviewer_logic.on_mount_logic = lambda app: None
reviewer_logic._update_detail_view = patched_update_detail_view
reviewer_logic.check_action_logic = patched_check_action_logic
reviewer_logic.toggle_selection_logic = patched_toggle_selection_logic
reviewer_logic.toggle_all_logic = patched_toggle_all_logic

# 2. Patch the app module's imported references
app_mod.on_mount_logic = lambda app: None
app_mod.check_action_logic = patched_check_action_logic
app_mod.toggle_selection_logic = patched_toggle_selection_logic
app_mod.toggle_all_logic = patched_toggle_all_logic

# 3. Completely sever the default ReviewerApp lifecycle
ReviewerApp.on_mount = lambda self: None
def patched_on_highlighted(self, event):
    if event.node and getattr(event.node.tree, "id", None) == "left-pane":
        patched_update_detail_view(self, event.node.data)
    self.refresh_bindings()
ReviewerApp.on_tree_node_highlighted = patched_on_highlighted

logger.debug("Successfully applied Total Override monkey-patches and severed lifecycle hooks.")

# --- Subclassed App ---

class PrototypeReviewerApp(ReviewerApp):
    def on_mount(self) -> None:
        """Manually trigger our guarded rebuild logic."""
        rebuild_prototype_tree(self)

    def on_tree_node_highlighted(self, event: Any) -> None:
        # Handled by class-level patch on ReviewerApp
        pass

    def action_jump_next(self) -> None:
        """Jump between Context -> Rationale -> Action Plan."""
        tree = self.query_one(ActionTree)
        node = tree.cursor_node
        if not node:
            tree.jump_to_section(CONTEXT_ROOT)
        elif node.data == CONTEXT_ROOT:
            tree.jump_to_section(ActionTree.RATIONALE_ROOT)
        elif node.data == ActionTree.RATIONALE_ROOT:
            tree.jump_to_section(ActionTree.ACTION_PLAN_ROOT)
        else:
            tree.jump_to_section(CONTEXT_ROOT)
        tree.focus()

    def action_jump_prev(self) -> None:
        """Jump between Action Plan -> Rationale -> Context."""
        tree = self.query_one(ActionTree)
        node = tree.cursor_node
        if not node:
            tree.jump_to_section(ActionTree.ACTION_PLAN_ROOT)
        elif node.data == ActionTree.ACTION_PLAN_ROOT:
            tree.jump_to_section(ActionTree.RATIONALE_ROOT)
        elif node.data == ActionTree.RATIONALE_ROOT:
            tree.jump_to_section(CONTEXT_ROOT)
        else:
            tree.jump_to_section(ActionTree.ACTION_PLAN_ROOT)
        tree.focus()

# --- Main Entry Point ---

if __name__ == "__main__":
    # 1. Create Mock Dependencies
    mock_env = MagicMock()
    mock_tooling = MagicMock()
    mock_dispatcher = MagicMock()
    
    # 2. Create Mock Plan
    plan = Plan(
        title="Prototype: Context Management",
        rationale="1. Synthesis\nTesting the new context UI.\n2. Justification\nEnsuring Zero-Touch isolation works.",
        actions=[
            ActionData(ActionType.CREATE, {"path": "test.txt", "content": "hello"}),
            ActionData(ActionType.EXECUTE, {"command": "ls -la"}),
        ]
    )
    
    # 3. Launch App
    app = PrototypeReviewerApp(
        plan=plan,
        system_env=mock_env,
        console_tooling=mock_tooling,
        action_dispatcher=mock_dispatcher
    )
    app.run()