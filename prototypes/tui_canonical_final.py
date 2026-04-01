# type: ignore
# ruff: noqa
import os
import shutil
import subprocess  # nosec B404
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Footer, Header, Input, Label, Static, Tree


class ActionTree(Tree):
    """A tree that allows both space and enter to toggle selection."""

    BINDINGS = [
        Binding("enter", "select_cursor", "Toggle", show=False),
    ]


class ParameterList(Tree):
    """A simple tree for displaying parameters."""


@dataclass
class MockAction:
    type: str
    params: Dict[str, Any]
    selected: bool = True
    modified: bool = False
    executed: bool = False
    state: str = "PENDING"  # PENDING, SUCCESS, FAILURE


class ParameterEditModal(ModalScreen[str]):
    """A modal for editing parameters."""

    BINDINGS = [("escape", "app.pop_screen", "Cancel")]

    def __init__(self, key: str, value: str):
        self.key, self.value = key, value
        super().__init__()

    def compose(self) -> ComposeResult:
        with Vertical(id="param-edit-dialog"):
            yield Label(f"Edit {self.key}:")
            yield Input(value=self.value, id="param-input")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)


class PromptOverlay(ModalScreen[bool]):
    """A non-invasive y/n prompt at the top of the screen."""

    def __init__(self, message: str):
        self.message = message
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Static(self.message, id="prompt-bar-overlay")

    def on_key(self, event) -> None:
        if event.key == "y":
            self.dismiss(True)
        elif event.key == "n":
            self.dismiss(False)


class StatusBar(Static):
    """A simple status bar for event logging."""

    def notify(self, message: str) -> None:
        self.update(message)


class CanonicalTuiPrototype(App):
    TITLE = "🟢 TeDDy Plan Review"
    CSS = """
    #main-container {
        layout: horizontal;
        height: 1fr;
    }
    #left-pane {
        width: 65%;
    }
    #right-pane {
        width: 35%;
        border-left: vkey $foreground 15%;
        padding: 0 1;
    }
    #prompt-bar-overlay { background: $primary; color: $text; padding: 0 1; height: 1; text-align: center; dock: top; }
    Tree { height: 1fr; }
    #status-bar { background: $boost; color: $text; height: 1; padding: 0 1; }
    #param-edit-dialog { background: $surface; padding: 1 2; width: 60%; height: auto; border: thick $primary; align: center middle; }
    """
    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("s", "submit", "Submit", show=True),
        Binding("space", "toggle_selection", "Toggle", show=True),
        Binding("x", "execute_step", "Execute", show=True),
        Binding("f", "fail_step", "Fail (Sim)", show=True),
        Binding("e", "edit_details", "Edit/Details", show=True),
        Binding("m", "add_message", "Message", show=True),
        Binding("r", "revert", "Revert", show=False),
    ]

    def __init__(self, actions: List[MockAction]):
        super().__init__()
        self.actions = actions
        self.editor = shutil.which("code") or shutil.which("vi") or shutil.which("nano")
        self.message_content = "This is the initial user message."
        self.INSTRUCTION_MARKER = (
            "\n\n<!-- Please enter your message above this line. -->"
        )

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-container"):
            yield ActionTree("Action Plan", id="left-pane")
            yield ParameterList("Parameters", id="right-pane")
        yield StatusBar("System Ready", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        action_tree = self.query_one(ActionTree)
        param_tree = self.query_one(ParameterList)

        param_tree.show_root = False
        action_tree.root.expand()

        for action in self.actions:
            node = action_tree.root.add_leaf("", data=action)
            self._update_node_label(node)

        action_tree.focus()
        self._update_detail_view(None)

    async def push_screen_wait(self, screen: Screen) -> Any:
        """Helper to push a screen and wait for its result."""
        return await self.push_screen(screen)

    def _update_node_label(self, node):
        action = node.data
        status_box = "[✓]" if action.selected else "[ ]"
        mod_tag = " *modified" if action.modified else ""
        summary = self._get_summary(action)

        if action.executed:
            color = "green" if action.state == "SUCCESS" else "red"
            label = f"[{color}][{action.state}] {action.type}: {summary}[/]"
        else:
            label = f"{status_box}{mod_tag} {action.type}: {summary}"
        node.label = label

    def _get_summary(self, action: MockAction) -> str:
        p = action.params
        summary = p.get("description") or p.get("path") or ""
        if action.type == "PROMPT" and not summary:
            summary = p.get("message", "").strip().split("\n")[0]
        summary = summary.strip().split("\n")[0]
        return summary[:60] + "..." if len(summary) > 60 else summary

    def on_tree_node_selected(self) -> None:
        self.action_toggle_selection()

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        if event.node.tree.id == "left-pane":
            action = event.node.data if not event.node.is_root else None
            self._update_detail_view(action)
        self.refresh_bindings()

    def _update_detail_view(self, action: Optional["MockAction"]):
        param_tree = self.query_one(ParameterList)
        param_tree.clear()
        param_tree.root.label = "Parameters"
        if action:
            param_tree.root.label = f"Parameters for {action.type}"
            for key, value in action.params.items():
                if key not in ("content", "find", "replace", "message"):
                    param_tree.root.add_leaf(f"{key}: {str(value)}")

    def check_action(self, action: str, _: tuple) -> bool:
        if action == "revert":
            node = self.query_one(ActionTree).cursor_node
            return bool(node and node.data and node.data.modified)
        return True

    def action_toggle_selection(self) -> None:
        node = self.query_one(ActionTree).cursor_node
        if node and not node.data.executed:
            node.data.selected = not node.data.selected
            self._update_node_label(node)

    def action_execute_step(self) -> None:
        node = self.query_one(ActionTree).cursor_node
        if node and not node.data.executed:
            node.data.executed = True
            node.data.state = "SUCCESS"
            self._update_node_label(node)
            self.query_one(StatusBar).notify(f"EXECUTED: {node.data.type}")

    def action_fail_step(self) -> None:
        node = self.query_one(ActionTree).cursor_node
        if node and not node.data.executed:
            node.data.executed = True
            node.data.state = "FAILURE"
            self._update_node_label(node)
            self.query_one(StatusBar).notify(f"FAILED: {node.data.type}")

    async def action_edit_details(self) -> None:
        node = self.query_one(ActionTree).cursor_node
        if not node:
            return
        action = node.data

        # This is a simplified version of the dual-pane logic
        # For this prototype, we'll just use a modal for a simple param
        if action.type == "EXECUTE":
            key, val = "command", action.params.get("command", "")
            new_val = await self.push_screen_wait(ParameterEditModal(key, val))
            if new_val is not None and new_val != val:
                action.params[key] = new_val
                action.modified = True
                self._update_node_label(node)
            return

        # For CREATE/EDIT, use external editor
        content = action.params.get(
            "content", f"# Content for {action.type} on {action.params.get('path', '')}"
        )
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w") as f:
            f.write(content)
            temp_path = f.name

        self.query_one(StatusBar).notify(
            f"LAUNCHING: {os.path.basename(self.editor)} {temp_path}"
        )
        subprocess.Popen([self.editor, temp_path])  # nosec B603

        res = await self.push_screen_wait(PromptOverlay("Submit manual changes? (y/n)"))
        if res:
            action.modified = True
            self._update_node_label(node)
            self.query_one(StatusBar).notify("Marked as modified.")
        os.unlink(temp_path)

    async def action_add_message(self) -> None:
        content = self.message_content + self.INSTRUCTION_MARKER
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w") as f:
            f.write(content)
            temp_path = f.name

        self.query_one(StatusBar).notify(
            f"LAUNCHING: {os.path.basename(self.editor)} {temp_path}"
        )
        proc = subprocess.Popen([self.editor, temp_path])
        proc.wait()  # In a real app this would be async

        with open(temp_path, "r") as f:
            new_content = f.read().split(self.INSTRUCTION_MARKER)[0].strip()
        self.message_content = new_content
        self.query_one(StatusBar).notify("Message updated (deferred save).")
        os.unlink(temp_path)

    def action_revert(self) -> None:
        node = self.query_one(ActionTree).cursor_node
        if node and node.data.modified:
            node.data.modified = False  # Simplistic revert for prototype
            self._update_node_label(node)
            self.query_one(StatusBar).notify("Reverted changes.")

    def action_submit(self) -> None:
        # Finalize message content here
        final_message = self.message_content
        self.exit(result=final_message)


if __name__ == "__main__":
    actions = [
        MockAction(
            "CREATE",
            {"path": "src/main.py", "description": "Create the app entry point"},
        ),
        MockAction(
            "EDIT", {"path": "pyproject.toml", "description": "Add new dependencies"}
        ),
        MockAction(
            "EXECUTE",
            {"command": "poetry install", "description": "Install dependencies"},
        ),
        MockAction(
            "PROMPT", {"message": "Does this approach look correct?", "description": ""}
        ),
    ]
    app = CanonicalTuiPrototype(actions)
    app.run()
