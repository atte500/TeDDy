import sys
import os
import re
from typing import Any

# Ensure we can import from src/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Tree, ContentSwitcher, Markdown, ListItem, Label
from textual.containers import Horizontal, VerticalScroll

# Import REAL widgets and CSS
from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
    ActionTree,
    ParameterDetail,
    DetailItem,
    TUI_CSS
)

# Constants for the plan
ALLOWED_SECTIONS = ["Synthesis", "Justification", "Expectation", "State Dashboard"]

class MockAction:
    def __init__(self, label, params):
        self.type = MagicMock()
        self.type.value = "CREATE"
        self.params = params
        self.description = label
        self.executed = False
        self.selected = True
        self.modified = False

from unittest.mock import MagicMock

class MockPlan:
    def __init__(self):
        self.title = "Test Plan"
        self.rationale = "0. test this should be ignored\n" +"1. Synthesis\n" + "Scroll testing... " * 100 + "\n\n2. Justification\nBecause...\n\n3. Expectation\nSpecific outcome.\n\n4. State Dashboard\nActive\n\n5. Random\nIgnore node, merge text."
        self.actions = [MockAction("CREATE file.txt", {"path": "file.txt"})]
        self.metadata = {"Status": "Planned", "Agent": "Prototyper"}
        self.is_session = False

class IntegratedRationaleSpike(App):
    CSS = TUI_CSS + """
    #right-pane {
        padding: 0;
        background: $surface;
    }
    #rationale-view {
        padding: 1 2;
        height: 1fr;
    }
    #rationale-content {
        background: transparent;
    }
    VerticalScroll {
        background: $surface;
    }
    """

    def __init__(self):
        super().__init__()
        self.plan = MockPlan()

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-container"):
            yield ActionTree("Action Plan", id="left-pane")
            with ContentSwitcher(id="right-pane", initial="params-view"):
                yield ParameterDetail(id="params-view")
                with VerticalScroll(id="rationale-view"):
                    yield Markdown(id="rationale-content")
        yield Footer()

    def on_mount(self) -> None:
        tree = self.query_one(ActionTree)
        tree.show_root = False
        tree.root.expand()

        # 1. Rationale with Sub-nodes (Approved UX)
        rat_root = tree.root.add("[bold]Rationale[/]", data="RATIONALE_ROOT", expand=True)
        sections = re.split(r"\n(?=### |\d+[\.\)]\s+)", "\n" + self.plan.rationale)
        current_node = None
        for section in sections:
            section = section.strip()
            if not section: continue
            lines = section.split("\n")
            title = re.sub(r"^(?:###\s*|\d+[\.\)]\s*)+", "", lines[0]).strip()
            if title in ALLOWED_SECTIONS:
                content = "\n".join(lines[1:]).strip()
                current_node = rat_root.add_leaf(title, data={"type": "RATIONALE_SECTION", "content": content})
            elif current_node:
                current_node.data["content"] += "\n\n" + section

        # 2. Action Root
        act_root = tree.root.add("[bold]Action Plan[/]", data="ACTION_PLAN_ROOT", expand=True)
        for action in self.plan.actions:
            # FIX: Use string value of enum in label
            type_str = action.type.value if hasattr(action.type, "value") else str(action.type)
            label = f"[v] {type_str}: {action.description}"
            act_root.add_leaf(label, data=action)

        tree.move_cursor(rat_root)
        tree.focus()

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        switcher = self.query_one(ContentSwitcher)
        data = event.node.data
        if data == "RATIONALE_ROOT":
            switcher.current = "params-view"
            pane = self.query_one("#params-view", ParameterDetail)
            pane.clear()
            pane.append(DetailItem("Agent", self.plan.metadata["Agent"]))
            pane.append(DetailItem("Status", self.plan.metadata["Status"]))
        elif isinstance(data, dict) and data.get("type") == "RATIONALE_SECTION":
            switcher.current = "rationale-view"
            # Show ONLY content (no redundant header)
            self.query_one("#rationale-content", Markdown).update(data["content"])
        elif hasattr(data, "params"):
            switcher.current = "params-view"
            pane = self.query_one("#params-view", ParameterDetail)
            pane.clear()
            for k, v in data.params.items():
                # Ensure Enum values are stringified
                val_str = v.value if hasattr(v, "value") else str(v)
                pane.append(DetailItem(k, val_str))

if __name__ == "__main__":
    IntegratedRationaleSpike().run()
