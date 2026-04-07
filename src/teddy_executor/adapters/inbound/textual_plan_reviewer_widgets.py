from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Input, Label, ListItem, ListView, Static, Tree

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


class ConfirmScreen(ModalScreen[bool]):
    """Modal screen for final confirmation."""

    def compose(self) -> ComposeResult:
        yield Label("Have you finished editing and saved the changes? (y/n)")

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
        from textual.containers import Vertical

        with Vertical(id="param_edit_container"):
            yield Label(self.label)
            yield Input(value=self.initial_value, id="param_input")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)


class StatusBar(Static):
    """A simple status bar for event logging."""

    def update_status(self, message: str) -> None:
        """Update the status bar content."""
        self.update(message)


class ActionTree(Tree):
    """A tree that allows both space and enter to toggle selection."""

    BINDINGS = [
        Binding("enter", "select_cursor", "Toggle", show=False),
        Binding("space", "select_cursor", "Toggle", show=False),
    ]


class ParameterDetail(ListView):
    """A focusable list that wraps parameters."""


class DetailItem(ListItem):
    """A focusable item in the parameter list."""

    def __init__(self, key: str, val: Any):
        super().__init__()
        self.data = {"key": key, "val": val}

    def compose(self) -> ComposeResult:
        """Compose the list item with a wrapping label."""
        from textual.widgets import Label

        yield Label(f"[bold]{self.data['key']}:[/] {self.data['val']}")
