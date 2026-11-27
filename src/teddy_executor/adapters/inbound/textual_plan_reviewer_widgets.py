from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Label, ListItem, ListView, Tree, Static

from teddy_executor.core.utils.string import canonical_agent_name

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


AGENT_CURRENT_MARKER = "(current)"


class AgentSelectScreen(ModalScreen[str]):
    """Modal screen for picking the session's agent persona.

    Dismisses the picked persona name, or ``None`` when abandoned, so an
    abandoned selection stays inert.
    """

    def __init__(self, agents: tuple[str, ...], current: str) -> None:
        super().__init__()
        self.agents = tuple(agents)
        self.current = canonical_agent_name(current)

    def compose(self) -> ComposeResult:
        yield Label("Select agent persona:")
        yield ListView(
            *[
                ListItem(
                    Label(
                        f"{name} {AGENT_CURRENT_MARKER}"
                        if name == self.current
                        else name
                    )
                )
                for name in self.agents
            ],
            id="agent-options",
        )

    def on_mount(self) -> None:
        view = self.query_one(ListView)
        view.index = self._current_index()
        view.focus()

    def _current_index(self) -> int:
        """Index of the persona already in force, defaulting to the first row."""
        if self.current in self.agents:
            return self.agents.index(self.current)
        return 0

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        index = event.list_view.index
        if index is not None and 0 <= index < len(self.agents):
            self.dismiss(self.agents[index])

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


class ActionTree(Tree):
    """A tree that allows both space and enter to toggle selection."""

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

    def jump_to_node(self, node: Any) -> None:
        """Move the cursor onto ``node``, expanding it and its ancestors first.

        A context subsection lives under the Context root, which starts
        collapsed, so expanding the whole lineage is what makes the destination
        visible. Expansion only schedules the line rebuild, so a previously
        hidden node still has no line this frame and ``move_cursor`` would
        record that as ``-1`` and move nowhere; the move is deferred until the
        lines exist. A target that already has a line moves immediately.
        """
        lineage = []
        current: Any = node
        while current is not None:
            lineage.append(current)
            current = current.parent
        for ancestor in reversed(lineage):
            ancestor.expand()
        if node.line < 0:
            self.call_after_refresh(self.move_cursor, node)
        else:
            self.move_cursor(node)


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


# The one gutter shared by both panes and every row inside them.
PANEL_INSET = (1, 2)

# A stylesheet cannot be formatted with str.format or string.Template: it
# carries literal {} blocks, percentage widths, and Textual $variables.
_INSET_SENTINEL = "__PANEL_INSET__"

_TUI_CSS_TEMPLATE = """
#main-container {
    layout: horizontal;
    height: 1fr;
}
#left-pane {
    width: 65%;
    padding: __PANEL_INSET__;
}
#right-pane {
    width: 35%;
    border-left: vkey $foreground 15%;
    padding: __PANEL_INSET__;
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
    background: transparent;
}
ListItem {
    height: auto;
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


def build_tui_css(inset: tuple[int, int]) -> str:
    """Render the reviewer stylesheet with ``inset`` applied to both panes.

    The inset is declared on the pane containers only, because CSS padding
    stacks: a child that declared its own would put that row back on a
    different gutter, which is the drift this inset exists to remove.
    """
    return _TUI_CSS_TEMPLATE.replace(_INSET_SENTINEL, f"{inset[0]} {inset[1]}")


TUI_CSS = build_tui_css(PANEL_INSET)
