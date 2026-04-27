from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, Optional, TypeVar, cast

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import ContentSwitcher, Footer, Header, ListView, Markdown, Tree

from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
    add_message_logic,
    check_action_logic,
    edit_action_logic,
    execute_step_logic,
    on_mount_logic,
    on_tree_node_highlighted,
    refresh_node_logic,
    revert_logic,
    toggle_all_logic,
    toggle_selection_logic,
    view_details_logic,
    view_plan_logic,
)
from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
    ActionTree,
    ParameterDetail,
    TUI_CSS,
)
from teddy_executor.core.services.edit_simulator import EditSimulator

logger = logging.getLogger(__name__)

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
        Binding("ctrl+down", "jump_next", "Next Section", show=False),
        Binding("alt+down", "jump_next", "Next Section", show=False),
        Binding("shift+down", "jump_next", "Next Section", show=False),
        Binding("ctrl+up", "jump_prev", "Prev Section", show=False),
        Binding("alt+up", "jump_prev", "Prev Section", show=False),
        Binding("shift+up", "jump_prev", "Prev Section", show=False),
        ("e", "edit_details", "Edit/Preview"),
        ("d", "view_details", "Details"),
        ("r", "revert", "Revert"),
        ("v", "view_plan", "View Plan"),
        ("x", "execute_step", "Execute Step"),
        ("m", "add_message", "Add Message"),
        ("q", "cancel", "Quit"),
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
        self._log_preview_files: list[str] = []

    def compose(self) -> ComposeResult:
        """
        Create child widgets for the app.
        """
        yield Header(show_clock=True)
        with Horizontal(id="main-container"):
            yield ActionTree("Action Plan", id="left-pane")
            with ContentSwitcher(id="right-pane", initial="params-view"):
                yield ParameterDetail(id="params-view")
                rationale_view = VerticalScroll(id="rationale-view")
                rationale_view.can_focus = True
                with rationale_view:
                    yield Markdown(id="rationale-content")
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
        # Check for the ParameterDetail widget or its container
        if control and getattr(control, "id", None) in ("right-pane", "params-view"):
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

        for f in getattr(self, "_log_preview_files", []):
            try:
                self._system_env.delete_file(f)
            except Exception:  # nosec B110
                logger.debug(f"Failed to delete temporary log preview file: {f}")

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
                    logger.debug(
                        f"Failed to remove pending temp file: {action.pending_temp_file}"
                    )

        for f in getattr(self, "_log_preview_files", []):
            try:
                self._system_env.delete_file(f)
            except Exception:  # nosec B110
                logger.debug(f"Failed to delete temporary log preview file: {f}")

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
        await view_details_logic(self)

    @work
    async def action_view_plan(self) -> None:
        """Open the full plan.md in an external editor."""
        await view_plan_logic(self)

    @work
    async def action_add_message(self) -> None:
        """Open the external editor to add/edit the user instruction message."""
        await add_message_logic(self)

    def action_focus_left(self) -> None:
        """Switch focus to the Action Tree."""
        self.query_one("#left-pane").focus()

    def action_focus_right(self) -> None:
        """Switch focus to the Parameter Detail pane."""
        self.query_one("#right-pane").focus()

    def action_jump_next(self) -> None:
        """Jump to the Action Plan section."""
        tree = self.query_one(ActionTree)
        tree.jump_to_section(ActionTree.ACTION_PLAN_ROOT)
        tree.focus()

    def action_jump_prev(self) -> None:
        """Jump to the Rationale section."""
        tree = self.query_one(ActionTree)
        tree.jump_to_section(ActionTree.RATIONALE_ROOT)
        tree.focus()

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
