from __future__ import annotations
from typing import Any, Optional

class PrototypeUiExtension:
    def extend_mount(self, app: Any) -> None:
        """Populate the action tree with prototype context data."""
        from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
            ActionTree, ContextFileData, SystemPromptData
        )
        tree = app.query_one(ActionTree)
        con_root = tree.root.add("[bold]Context[/]", data="CONTEXT_ROOT", expand=False)
        con_root.add_leaf("[#888888 italic]System:[/]", data="SYSTEM_LABEL")
        prompt_data = SystemPromptData("Architect", 2500)
        con_root.add_leaf(f"  {prompt_data.agent}", data=prompt_data)
        con_root.add_leaf("[#888888 italic]Session:[/]", data="SESSION_LABEL")
        
        sim_data = [
            ("src/core.py", 1200, "  ", True, "Session", None),
            ("src/utils.py", 450, "M", True, "Session", None),
            ("docs/plan-INVALID.md", 300, "??", False, "Turn", "Failed plan validation"),
            ("reports/turn-01-FAILURE.md", 1500, "  ", False, "Turn", "Non-green plan"),
            ("src/heavy_logic.py", 15000, "M", False, "Turn", "Exceeds 15k token limit"),
        ]

        for path, tokens, status, selected, scope, reason in sim_data:
            if scope == "Turn" and not any(n.data == "TURN_LABEL" for n in con_root.children):
                con_root.add_leaf("[#888888 italic]Turn:[/]", data="TURN_LABEL")
            file_data = ContextFileData(path, tokens, status, scope, selected, reason)
            con_root.add_leaf(file_data.format_label(), data=file_data)

    def handle_details(self, app: Any, data: Any, switcher: Any) -> bool:
        """Helper to process prototype detail views."""
        from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
            ParameterDetail, DetailItem, ContextFileData, SystemPromptData
        )
        if not isinstance(data, (ContextFileData, SystemPromptData)) and data not in (
            "CONTEXT_ROOT", "SYSTEM_LABEL", "SESSION_LABEL", "TURN_LABEL"
        ):
            return False

        pane = app.query_one(ParameterDetail)
        switcher.current = "params-view"
        pane.clear()

        if isinstance(data, ContextFileData):
            pane.append(DetailItem("Path", data.path))
            pane.append(DetailItem("Tokens", f"{data.tokens / 1000.0:.1f}k"))
            status_map = {"M": "Modified", "??": "Untracked", "A": "Added", "D": "Deleted"}
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
            session_k, turn_k, prompt_k = 1.95, 16.5, 2.5
            total_k = session_k + turn_k + prompt_k
            pane.append(DetailItem("Total Context", f"{total_k:.1f}k / 128k tokens"))
            pane.append(DetailItem("", ""))
            pane.append(DetailItem("• System", f"{prompt_k:.1f}k"))
            pane.append(DetailItem("• Session", f"{session_k:.1f}k"))
            pane.append(DetailItem("• Turn", f"{turn_k:.1f}k"))
        return True

    def handle_edit(self, app: Any, data: Any) -> bool:
        """Helper to process prototype edit requests."""
        from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
            ContextFileData, SystemPromptData
        )
        if data in ("SESSION_LABEL", "TURN_LABEL", "SYSTEM_LABEL", "CONTEXT_ROOT") or \
           isinstance(data, (ContextFileData, SystemPromptData)):
            return True
        return False

    def handle_binding(self, app: Any, action_name: str, node: Any) -> Optional[bool]:
        """Helper to process prototype binding checks."""
        from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
            ContextFileData, SystemPromptData
        )
        if node and (node.data in ("SESSION_LABEL", "TURN_LABEL", "CONTEXT_ROOT") or 
                     isinstance(node.data, (ContextFileData, SystemPromptData))):
            return action_name in ("edit_details", "cancel", "focus_right", 
                                   "focus_left", "jump_next", "jump_prev")
        return None

    def handle_selection(self, app: Any, node: Any) -> bool:
        """Helper to process prototype selection toggles."""
        from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
            ContextFileData
        )
        if node.data in ("SESSION_LABEL", "TURN_LABEL", "CONTEXT_ROOT"):
            return True
        if isinstance(node.data, ContextFileData):
            node.data.selected = not node.data.selected
            node.label = node.data.format_label()
            return True
        return False

    def handle_toggle_all(self, app: Any, node: Any, new_state: bool) -> bool:
        """Helper to process prototype toggle-all behavior."""
        from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
            ContextFileData
        )
        if isinstance(node.data, ContextFileData):
            node.data.selected = new_state
            node.label = node.data.format_label()
            return True
        return False