from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Label, ListItem, ListView, Tree, Static

if TYPE_CHECKING:
    from textual.app import ComposeResult


class PathInputScreen(ModalScreen[str]):
    """Modal screen for editing a file path."""

    def __init__(self, initial_path: str):
        super().__init__()
        self.initial_path = initial_path

    def compose(self) -> ComposeResult:
        yield Label("File path:")
        yield Input(value=self.initial_path, id="path_input")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


class ConfirmScreen(ModalScreen[bool]):
    """Modal screen for final confirmation."""

    def __init__(self, message: str = "Do you want to apply the changes? (y/n)"):
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        yield Label(self.message)

    def on_key(self, event) -> None:
        if event.key == "y":
            self.dismiss(True)
        elif event.key == "n":
            self.dismiss(False)


class ParameterEditModal(ModalScreen[str]):
    """Modal screen for editing a simple parameter string."""

    def __init__(self, label: str, initial_value: str):
        super().__init__()
        self.label = label
        self.initial_value = initial_value

    def compose(self) -> ComposeResult:
        yield Label(self.label)
        yield Input(value=self.initial_value, id="param_input")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


class ActionTree(Tree):
    """A tree that allows both space and enter to toggle selection."""

    CONTEXT_ROOT = "CONTEXT_ROOT"
    RATIONALE_ROOT = "RATIONALE_ROOT"
    ACTION_PLAN_ROOT = "ACTION_PLAN_ROOT"

    BINDINGS = [
        Binding("enter", "select_cursor", "Toggle", show=False),
        Binding("space", "select_cursor", "Toggle", show=False),
        Binding(
            "ctrl+down",
            "app.jump_next",
            "Next Section",
            show=False,
            priority=True,
        ),
        Binding("alt+down", "app.jump_next", "Next Section", show=False, priority=True),
        Binding(
            "shift+down",
            "app.jump_next",
            "Next Section",
            show=False,
            priority=True,
        ),
        Binding("ctrl+up", "app.jump_prev", "Prev Section", show=False, priority=True),
        Binding("alt+up", "app.jump_prev", "Prev Section", show=False, priority=True),
        Binding(
            "shift+up",
            "app.jump_prev",
            "Prev Section",
            show=False,
            priority=True,
        ),
    ]

    def jump_to_section(self, section_id: str) -> None:
        """
        Jump focus to a major section node.

        Args:
            section_id: The identifier for the section (e.g., RATIONALE_ROOT).
        """
        for child in self.root.children:
            if child.data == section_id:
                # Ensure the section is expanded and visible before moving cursor
                child.expand()
                self.move_cursor(child)
                # Ensure parent is also expanded (root is usually invisible but its children should be shown)
                self.root.expand()
                return


class RationaleDetail(VerticalScroll):
    """A focusable scroll view for rationale."""

    BINDINGS = [
        Binding("shift+up", "scroll_to_top", "Top", show=False, priority=True),
        Binding("shift+down", "scroll_to_bottom", "Bottom", show=False, priority=True),
        Binding("alt+up", "scroll_to_top", "Top", show=False, priority=True),
        Binding("alt+down", "scroll_to_bottom", "Bottom", show=False, priority=True),
        Binding("ctrl+up", "scroll_to_top", "Top", show=False, priority=True),
        Binding("ctrl+down", "scroll_to_bottom", "Bottom", show=False, priority=True),
    ]

    def action_scroll_to_top(self) -> None:
        """Scroll to the top of the content."""
        self.scroll_home(animate=False)

    def action_scroll_to_bottom(self) -> None:
        """Scroll to the bottom of the content."""
        self.scroll_end(animate=False)


class ParameterDetail(ListView):
    """A focusable list that wraps parameters."""

    BINDINGS = [
        Binding("shift+up", "scroll_to_top", "Top", show=False, priority=True),
        Binding("shift+down", "scroll_to_bottom", "Bottom", show=False, priority=True),
        Binding("alt+up", "scroll_to_top", "Top", show=False, priority=True),
        Binding("alt+down", "scroll_to_bottom", "Bottom", show=False, priority=True),
        Binding("ctrl+up", "scroll_to_top", "Top", show=False, priority=True),
        Binding("ctrl+down", "scroll_to_bottom", "Bottom", show=False, priority=True),
    ]

    def action_scroll_to_top(self) -> None:
        """Jump focus to the first item."""
        if self.children:
            self.index = 0

    def action_scroll_to_bottom(self) -> None:
        """Jump focus to the last item."""
        if self.children:
            self.index = len(self.children) - 1


class DetailItem(ListItem):
    """A focusable item in the parameter list."""

    MAX_PREVIEW_LENGTH = 20000
    TRUNCATE_HALFWAY = 10000

    def __init__(self, key: str, val: Any):
        super().__init__()
        # Truncate extremely large values to prevent TUI freeze during layout
        display_val = str(val)
        if len(display_val) > self.MAX_PREVIEW_LENGTH:
            display_val = (
                display_val[: self.TRUNCATE_HALFWAY]
                + "\n\n... [TRUNCATED FOR PREVIEW] ...\n\n"
                + display_val[-self.TRUNCATE_HALFWAY :]
            )
        self.data = {"key": key, "val": val, "display_val": display_val}

    def compose(self) -> ComposeResult:
        """Compose the list item with a wrapping static widget."""
        # Use Static instead of Label for performance on large content
        content = self.data["display_val"]
        if self.data["key"]:
            content = f"[bold]{self.data['key']}:[/] {content}"
        yield Static(content, expand=True)


TUI_CSS = """
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
    padding: 0;
    background: $surface;
}
#right-pane:focus-within {
    background: $surface-lighten-1;
}
Tree {
    height: 1fr;
}
ListView {
    background: transparent;
    height: 1fr;
    border: none;
}
VerticalScroll {
    background: transparent;
}
#rationale-content {
    padding: 1 2;
    background: transparent;
}
ListItem {
    height: auto;
    padding: 0 1;
}
ListItem.--highlight {
    background: $accent 30%;
    color: $text;
    text-style: bold;
}
Static {
    width: 100%;
    height: auto;
}
"""
