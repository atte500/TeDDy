# type: ignore
# ruff: noqa
import os
import shutil
import subprocess  # nosec B404
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
    Tree,
)


@dataclass
class ActionLog:
    status: str
    details: Optional[str] = None
    failed_command: Optional[str] = None


@dataclass
class MockAction:
    type: str
    params: Dict[str, Any]
    description: str = ""
    selected: bool = True
    modified: bool = False
    executed: bool = False
    state: str = "PENDING"
    action_log: Optional[ActionLog] = None
    pending_temp_file: Optional[str] = None


class ActionTree(Tree):
    BINDINGS = [
        Binding("enter", "select_cursor", "Toggle", show=False),
        Binding("space", "select_cursor", "Toggle", show=False),
    ]


class ParameterDetail(ListView):
    """A focusable list that wraps parameters."""

    pass


class DetailItem(ListItem):
    """A focusable item in the parameter list."""

    def __init__(self, key: str, val: Any):
        super().__init__()
        self.data = {"key": key, "val": val}

    def compose(self) -> ComposeResult:
        # Use a single Label to allow label and value to wrap together on the same line
        yield Label(f"[bold]{self.data['key']}:[/] {self.data['val']}")


class ParameterEditModal(ModalScreen[str]):
    """A modal for editing simple parameters in-TUI."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "submit", "Submit"),
    ]

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_submit(self) -> None:
        self.dismiss(self.query_one(Input).value)

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
    """A simple y/n prompt."""

    BINDINGS = [
        Binding("y", "confirm", "Yes"),
        Binding("n", "cancel", "No"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def __init__(self, message: str):
        self.message = message
        super().__init__()

    def compose(self) -> ComposeResult:
        s = Static(self.message, id="prompt-bar-overlay")
        s.can_focus = True
        yield s

    def on_mount(self) -> None:
        self.query_one(Static).focus()


class EnterConfirmOverlay(ModalScreen[bool]):
    """A simple enter-to-confirm prompt."""

    BINDINGS = [
        Binding("enter", "confirm", "Confirm"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def __init__(self, message: str):
        self.message = message
        super().__init__()

    def compose(self) -> ComposeResult:
        s = Static(self.message, id="prompt-bar-overlay")
        s.can_focus = True
        yield s

    def on_mount(self) -> None:
        self.query_one(Static).focus()


class StatusBar(Static):
    def notify(self, message: str) -> None:
        self.update(message)


class DeferredHarvestTui(App):
    CSS = """
    #main-container { layout: horizontal; height: 1fr; }
    #left-pane { width: 65%; }
    #right-pane { width: 35%; border-left: vkey $foreground 15%; padding: 0; }
    #status-bar { background: $boost; color: $text; height: 1; padding: 0 1; dock: bottom; }
    #prompt-bar-overlay { background: $primary; color: $text; padding: 0 1; height: 1; text-align: center; dock: top; }
    #param-edit-dialog { background: $surface; padding: 1 2; width: 60%; height: auto; border: thick $primary; align: center middle; }
    Tree { height: 1fr; }
    ListView { background: $surface; height: 1fr; border: none; }
    ListItem { height: auto; padding: 0 1; }
    ListItem Label { width: 100%; height: auto; }
    .detail-header { width: 100%; text-align: center; color: $text-muted; padding: 1; background: $boost; }
    """

    TITLE = "🟢 TeDDy Refined Plan Review"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("s", "submit", "Submit"),
        Binding("e", "edit_details", "Edit"),
        Binding("x", "execute_step", "Execute"),
        Binding("m", "add_message", "Message"),
    ]

    def __init__(self, actions: List[MockAction]):
        super().__init__()
        self.actions = actions
        self.editor = shutil.which("code") or shutil.which("vi")
        self.user_message_temp = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-container"):
            yield ActionTree("Action Plan", id="left-pane")
            yield ParameterDetail(id="right-pane")
        yield StatusBar("System Ready", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        action_tree = self.query_one(ActionTree)
        action_tree.root.expand()

        for action in self.actions:
            node = action_tree.root.add_leaf("", data=action)
            self._update_node_label(node)

        action_tree.focus()
        self._update_detail_view(None)

    def _update_node_label(self, node):
        action = node.data
        status_box = "[✓]" if action.selected else "[ ]"
        mod_tag = " *modified" if action.modified else ""

        summary = action.description or action.type
        # Truncate summary for information density
        if len(summary) > 60:
            summary = summary[:57] + "..."

        if action.type == "PROMPT":
            msg = action.params.get("message", "").strip().split("\n")[0]
            summary = msg[:60] + "..." if len(msg) > 60 else msg

        if action.executed:
            color = "green" if action.state == "SUCCESS" else "red"
            label = f"[{color}][{action.state}] {action.type}: {summary}[/]"
        else:
            # *modified is now a suffix at the end of the label
            label = f"{status_box} {action.type}: {summary}{mod_tag}"
        node.label = label

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        self.action_toggle_selection()

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        if event.node and getattr(event.node.tree, "id", None) == "left-pane":
            action = event.node.data if not event.node.is_root else None
            self._update_detail_view(action)

    def action_toggle_selection(self) -> None:
        tree = self.query_one("#left-pane", ActionTree)
        node = tree.cursor_node
        if node and node.data and not node.data.executed:
            node.data.selected = not node.data.selected
            self._update_node_label(node)

    def _update_detail_view(self, action: Optional[MockAction]):
        pane = self.query_one(ParameterDetail)
        pane.clear()

        if not action:
            pane.mount(ListItem(Label("Select an action to view details")))
            return

        if action.executed and action.action_log:
            log = action.action_log
            pane.mount(ListItem(Label(f"[bold]LOG:[/] {action.type}")))
            pane.mount(ListItem(Label(f"[bold]status:[/] {log.status}")))
            if log.details:
                pane.mount(ListItem(Label(f"[bold]details:[/] {log.details}")))
            if log.failed_command:
                pane.mount(
                    ListItem(Label(f"[bold]failed_cmd:[/] {log.failed_command}"))
                )
            return

        # Config Defaults Mock
        defaults = {
            "timeout": 30.0,
            "overwrite": False,
            "match_all": False,
            "allow_failure": False,
            "background": False,
            "reference_files": "[]",
        }

        param_map = {
            "CREATE": ["path", "overwrite"],
            "EDIT": ["path", "match_all"],
            "EXECUTE": ["command", "allow_failure", "background", "timeout"],
            "PROMPT": ["message", "reference_files"],
        }

        keys = param_map.get(action.type, [])
        for key in keys:
            val = action.params.get(key, defaults.get(key, ""))
            pane.append(DetailItem(key, val))

    def on_focus(self, event):
        """Auto-focus first param when right pane gets focus via Tab."""
        control = getattr(event, "control", None)
        if control and getattr(control, "id", None) == "right-pane":
            list_view = self.query_one(ParameterDetail)
            if list_view.children:
                list_view.index = 0

    @work
    async def action_execute_step(self) -> None:
        node = self.query_one(ActionTree).cursor_node
        if node and node.data and not node.data.executed:
            action = node.data
            if action.type == "PROMPT":
                # Manual PROMPT execution triggers the editor reply loop
                await self._launch_external_editor(
                    action,
                    "user_response",
                    "",
                    node,
                    prompt="Reply to PROMPT (press enter to confirm)",
                    use_enter=True,
                )
                action.executed = True
                action.state = "SUCCESS"
                action.action_log = ActionLog(
                    status="SUCCESS", details=f"Response captured."
                )
            else:
                action.executed = True
                action.state = "SUCCESS"
                action.action_log = ActionLog(
                    status="SUCCESS", details="Applied successfully."
                )

            self._update_node_label(node)
            self._update_detail_view(node.data)
            self.query_one(StatusBar).notify(f"EXECUTED: {action.type}")

    @work
    async def action_edit_details(self) -> None:
        node = self.query_one(ActionTree).cursor_node
        if not node or not node.data:
            return
        action = node.data

        # Check if focus is in the right pane (ListView)
        list_view = self.query_one(ParameterDetail)
        if list_view.has_focus:
            item = list_view.highlighted_child
            if item and hasattr(item, "data"):
                key, val = item.data["key"], item.data["val"]
                if key in ("content", "command", "message", "queries"):
                    await self._launch_external_editor(action, key, val, node)
                else:
                    new_val = await self.push_screen_wait(
                        ParameterEditModal(key, str(val))
                    )
                    if new_val is not None and str(new_val) != str(val):
                        action.params[key] = new_val
                        action.modified = True
                        self._update_node_label(node)
                        self._update_detail_view(action)
            return

        # Default: Edit primary content
        primary_key = {
            "EXECUTE": "command",
            "PROMPT": "message",
            "CREATE": "content",
            "EDIT": "content",
        }.get(action.type)
        if primary_key:
            await self._launch_external_editor(
                action, primary_key, action.params.get(primary_key, ""), node
            )

    async def _launch_external_editor(
        self, action, key, val, node, prompt=None, use_enter=False
    ):
        if action.pending_temp_file and os.path.exists(action.pending_temp_file):
            path = action.pending_temp_file
        else:
            fd, path = tempfile.mkstemp(suffix=".md")
            os.close(fd)
            with open(path, "w") as f:
                f.write(str(val))

        self.query_one(StatusBar).notify(
            f"OPENED: {os.path.basename(self.editor)} {path}"
        )
        subprocess.Popen([self.editor, path])  # nosec B603

        if use_enter:
            res = await self.push_screen_wait(
                EnterConfirmOverlay(prompt or "Press enter to confirm")
            )
        else:
            res = await self.push_screen_wait(
                PromptOverlay(prompt or "Save manual changes? (y/n)")
            )

        if res:
            action.pending_temp_file = path
            action.modified = True
            self._update_node_label(node)
            self.query_one(StatusBar).notify("Marked as modified.")

    @work
    async def action_add_message(self) -> None:
        fd, path = tempfile.mkstemp(suffix=".md")
        os.close(fd)
        self.user_message_temp = path
        subprocess.Popen([self.editor, path])  # nosec B603
        self.query_one(StatusBar).notify(f"MESSAGE EDITOR OPENED: {path}")

    def action_revert(self) -> None:
        node = self.query_one(ActionTree).cursor_node
        if node and node.data and node.data.modified:
            node.data.modified = False
            self._update_node_label(node)
            self.query_one(StatusBar).notify("Reverted changes.")

    def action_submit(self) -> None:
        self.query_one(StatusBar).notify("Harvesting changes...")
        # Harvesting deferred changes
        for action in self.actions:
            if action.pending_temp_file:
                # In real app: read file, apply content, delete file
                self.query_one(StatusBar).notify(
                    f"Harvested {action.type} from {action.pending_temp_file}"
                )
                os.remove(action.pending_temp_file)

        if self.user_message_temp:
            self.query_one(StatusBar).notify(
                f"Harvested User Message from {self.user_message_temp}"
            )
            os.remove(self.user_message_temp)

        self.exit("Plan submitted with harvested changes.")


if __name__ == "__main__":
    actions = [
        MockAction(
            "CREATE", {"path": "src/main.py"}, description="Initialize app entry point"
        ),
        MockAction(
            "EXECUTE",
            {
                "command": "pytest --cov=src --cov-report=term-missing --cov-report=xml --junitxml=reports/junit.xml"
            },
            description="Run comprehensive test suite with coverage and reporting enabled to verify all system behaviors",
        ),
        MockAction(
            "PROMPT",
            {
                "message": "Should we include the new logging module in the initial bootstrap?"
            },
        ),
    ]
    app = DeferredHarvestTui(actions)
    app.run()
