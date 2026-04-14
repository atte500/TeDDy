from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Optional, TypeVar, cast

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Footer, Header, ListView, Tree

from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
    check_action_logic,
    edit_action_logic,
    execute_step_logic,
    on_mount_logic,
    on_tree_node_highlighted,
    refresh_node_logic,
    revert_logic,
    toggle_all_logic,
    toggle_selection_logic,
)
from teddy_executor.adapters.inbound.textual_plan_reviewer_previews import (
    launch_editor,
)
from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
    ActionTree,
    ParameterDetail,
    TUI_CSS,
)
from teddy_executor.core.services.edit_simulator import EditSimulator

if TYPE_CHECKING:
    from teddy_executor.core.domain.models.plan import Plan
    from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
    from teddy_executor.core.ports.outbound.file_system_manager import (
        IFileSystemManager,
    )
    from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper
    from teddy_executor.core.services.action_dispatcher import ActionDispatcher

T = TypeVar("T")


class ReviewerApp(App):
    """
    The Textual application for reviewing and modifying plans.
    """

    INSTRUCTION_MARKER = "\n\n<!-- Please enter your response above this line. -->"

    BINDINGS = [
        ("s", "submit", "Submit"),
        ("a", "toggle_all", "Toggle All"),
        ("e", "edit_details", "Edit/Preview"),
        ("d", "view_details", "Details"),
        ("r", "revert", "Revert"),
        ("v", "view_plan", "View Plan"),
        ("x", "execute_step", "Execute Step"),
        ("m", "add_message", "Add Message"),
        ("q", "cancel", "Cancel"),
        ("left", "focus_left", "Focus Left"),
        ("right", "focus_right", "Focus Right"),
    ]

    CSS = TUI_CSS

    def __init__(
        self,
        plan: Plan,
        system_env: ISystemEnvironment,
        console_tooling: ConsoleToolingHelper,
        action_dispatcher: ActionDispatcher,
        file_system: Optional[IFileSystemManager] = None,
    ):
        super().__init__()
        self.plan = plan
        self._system_env = system_env
        self._console_tooling = console_tooling
        self._action_dispatcher = action_dispatcher
        self._file_system = file_system
        self._edit_simulator = EditSimulator()
        self._user_message_cache: Optional[str] = None

    def compose(self) -> ComposeResult:
        """
        Create child widgets for the app.
        """
        yield Header(show_clock=True)
        with Horizontal(id="main-container"):
            yield ActionTree("Action Plan", id="left-pane")
            yield ParameterDetail(id="right-pane")
        yield Footer()

    def on_mount(self) -> None:
        """Populate the action tree when the app is mounted."""
        on_mount_logic(self)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Toggle action selection when a node is selected."""
        toggle_selection_logic(self, event.node)

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        """Refresh footer bindings when a new node is highlighted."""
        on_tree_node_highlighted(self, event)

    @work
    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle parameter editing when an item is selected in the right pane."""
        from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
            on_list_view_selected_logic,
        )

        await on_list_view_selected_logic(self, event.item)

    def on_descendant_focus(self, event: Any) -> None:
        """Auto-focus first param when right pane gets focus via Tab."""
        control = getattr(event, "control", None)
        if control and getattr(control, "id", None) == "right-pane":
            list_view = self.query_one(ParameterDetail)
            if list_view.children:
                list_view.index = 0

    def check_action(self, action: str, parameters: tuple[Any, ...]) -> bool:
        """Gate for enabling/disabling bindings based on state."""
        _ = parameters
        return check_action_logic(self, action)

    def action_revert(self) -> None:
        """Revert manual modifications for the currently highlighted action."""
        tree = self.query_one(Tree)
        if tree.cursor_node:
            revert_logic(self, tree.cursor_node)

    @work(exclusive=True)
    async def action_execute_step(self) -> None:
        """Executes the currently highlighted action as a background worker."""
        tree = self.query_one(Tree)
        if tree.cursor_node:
            await execute_step_logic(self, tree.cursor_node)

    def action_submit(self) -> None:
        """Exit the app and return the modified plan."""
        # Harvest deferred changes from pending_temp_files
        for action in self.plan.actions:
            self._harvest_action_content(action)

        if self._user_message_cache is not None:
            marker = self.INSTRUCTION_MARKER.strip()
            if marker in self._user_message_cache:
                final_message: str = self._user_message_cache.split(marker)[0].strip()
            else:
                final_message = self._user_message_cache.strip()
            self.plan.metadata["user_request"] = final_message
        self.exit(self.plan)

    def action_cancel(self) -> None:
        """Exit the app and return None (cancellation)."""
        # Cleanup any pending temp files
        for action in self.plan.actions:
            # Type guard for Mocks in tests
            is_valid_path = isinstance(action.pending_temp_file, (str, os.PathLike))
            if (
                action.pending_temp_file
                and is_valid_path
                and os.path.exists(action.pending_temp_file)
            ):
                try:
                    os.remove(action.pending_temp_file)
                    action.pending_temp_file = None
                except Exception:  # nosec B110
                    pass
        self.exit(None)

    @work
    async def action_edit_details(self) -> None:
        """Edit or preview the currently highlighted action or parameter."""
        tree = self.query_one(Tree)
        node = tree.cursor_node
        if not node or not node.data:
            return

        from teddy_executor.core.domain.models.plan import ActionData

        if isinstance(node.data, ActionData) and node.data.executed:
            # Edit is disabled for executed actions; redirect to view_details
            await cast(Any, self.action_view_details())
            return

        # Check if the right pane or any of its children has focus
        right_pane = self.query_one(ParameterDetail)
        is_right_pane_focused = right_pane.has_focus or (
            self.focused and self.focused in right_pane.query("*")
        )

        if is_right_pane_focused and right_pane.highlighted_child:
            from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
                on_list_view_selected_logic,
            )

            await on_list_view_selected_logic(self, right_pane.highlighted_child)
            return

        await edit_action_logic(self, node, node.data)

    @work
    async def action_view_details(self) -> None:
        """View full execution logs or complex action details in an editor."""
        tree = self.query_one(Tree)
        node = tree.cursor_node
        if not node or not node.data:
            return

        from teddy_executor.core.domain.models.plan import ActionData
        from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
            format_action_log,
        )

        action = node.data
        if not isinstance(action, ActionData) or not action.executed:
            return

        if action.action_log:
            log_content = format_action_log(action.action_log)
            await launch_editor(self, log_content, suffix=".md", skip_confirm=True)

    @work
    async def action_view_plan(self) -> None:
        """Open the full plan.md in an external editor."""
        content: Optional[str] = None
        if self.plan.plan_path and self._file_system:
            try:
                content = self._file_system.read_file(self.plan.plan_path)
            except Exception:  # nosec B110
                pass
        if not content:
            content = self.plan.raw_content
        if not content:
            content = f"# Plan: {self.plan.title}\n\n{self.plan.rationale}\n\n"
        if content:
            await launch_editor(self, content, suffix=".md")

    @work
    async def action_add_message(self) -> None:
        """Open the external editor to add/edit the user instruction message."""
        current_message = self._user_message_cache
        if current_message is None:
            current_message = self.plan.metadata.get("user_request") or ""
            if self.INSTRUCTION_MARKER not in current_message:
                current_message += self.INSTRUCTION_MARKER
        new_message = await launch_editor(self, current_message, suffix=".md")
        if new_message is not None and new_message != current_message:
            self._user_message_cache = new_message

    def action_focus_left(self) -> None:
        """Switch focus to the Action Tree."""
        self.query_one("#left-pane").focus()

    def action_focus_right(self) -> None:
        """Switch focus to the Parameter Detail pane."""
        self.query_one("#right-pane").focus()

    def action_toggle_all(self) -> None:
        """Toggle selection for all actions."""
        toggle_all_logic(self, self.plan)

    def _refresh_node(self, node: Any) -> None:
        """Refresh the label and state of a single tree node."""
        refresh_node_logic(self, node)

    def _harvest_action_content(self, action: Any) -> None:
        """Harvest modified content from a pending temporary file back to the action."""
        from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
            harvest_action_content,
        )

        harvest_action_content(action, self.INSTRUCTION_MARKER)
