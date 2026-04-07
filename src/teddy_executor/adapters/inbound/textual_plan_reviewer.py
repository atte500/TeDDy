from __future__ import annotations

import asyncio
import os
from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any, Optional, TypeVar, Union

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Header, Tree

from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
    check_action_logic,
    edit_action_logic,
    execute_step_logic,
    launch_editor,
    on_mount_logic,
    refresh_node_logic,
    revert_logic,
    toggle_all_logic,
    toggle_selection_logic,
)
from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
    ActionTree,
    ConfirmScreen,
    ParameterDetail,
    StatusBar,
)
from teddy_executor.core.domain.models.plan import Plan
from teddy_executor.core.services.action_dispatcher import ActionDispatcher
from teddy_executor.core.services.edit_simulator import EditSimulator

if TYPE_CHECKING:
    from teddy_executor.core.domain.models.plan import ActionData

from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper


# Widgets and Screens extracted to textual_plan_reviewer_widgets.py


T = TypeVar("T")


class ReviewerApp(App):
    """
    The Textual application for reviewing and modifying plans.
    """

    INSTRUCTION_MARKER = "\n\n<!-- Please enter your message above this line. -->"

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
        padding: 0;
    }
    #status_bar {
        background: $boost;
        color: $text;
        height: 1;
        padding: 0 1;
        dock: bottom;
    }
    Tree {
        height: 1fr;
    }
    ListView {
        background: $surface;
        height: 1fr;
        border: none;
    }
    ListItem {
        height: auto;
        padding: 0 1;
    }
    ListItem Label {
        width: 100%;
        height: auto;
    }
    """

    BINDINGS = [
        ("s", "submit", "Submit"),
        ("a", "toggle_all", "Toggle All"),
        ("e", "edit_details", "Edit"),
        ("r", "revert", "Revert"),
        ("v", "view_plan", "View Plan"),
        ("x", "execute_step", "Execute Step"),
        ("m", "add_message", "Add Message"),
        ("q", "cancel", "Cancel"),
    ]

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
        yield StatusBar("System Ready", id="status_bar")
        yield Footer()

    def push_screen_wait(
        self, screen: Union[Screen[T], str], *, mode: Optional[str] = None
    ) -> Coroutine[Any, Any, T]:
        """Push a screen and wait for its dismissal result."""
        _ = mode
        loop = asyncio.get_event_loop()
        future: asyncio.Future[T] = loop.create_future()

        def _callback(result: Optional[T]) -> None:
            if not future.done():
                future.set_result(result)  # type: ignore[arg-type]

        self.push_screen(screen, callback=_callback)  # type: ignore[arg-type]
        return future  # type: ignore[return-value]

    def on_mount(self) -> None:
        """Populate the action tree when the app is mounted."""
        on_mount_logic(self)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Toggle action selection when a node is selected."""
        toggle_selection_logic(self, event.node)

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        """Refresh footer bindings when a new node is highlighted."""
        if event.node.tree.id == "left-pane":
            action = event.node.data if not event.node.is_root else None
            self._update_detail_view(action)
        self.refresh_bindings()

    def _update_detail_view(self, action: Optional[ActionData]) -> None:
        """Update the parameter list with the highlighted action's details."""
        param_pane = self.query_one(ParameterDetail)
        param_pane.clear()
        if not action:
            from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
                DetailItem,
            )

            param_pane.append(
                DetailItem(key="Info", val="Select an action to view details")
            )

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
        if self._user_message_cache is not None:
            final_message: str = self._user_message_cache.split(
                self.INSTRUCTION_MARKER
            )[0].strip()
            self.plan.metadata["user_request"] = final_message
        self.exit(self.plan)

    def action_cancel(self) -> None:
        """Exit the app and return None (cancellation)."""
        self.exit(None)

    @work
    async def action_edit_details(self) -> None:
        """Edit or preview the currently highlighted action."""
        tree = self.query_one(Tree)
        node = tree.cursor_node
        if not node or not node.data:
            return
        await edit_action_logic(self, node, node.data)

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
        if new_message is not None:
            if await self.push_screen_wait(ConfirmScreen()):
                self._user_message_cache = new_message

    def action_toggle_all(self) -> None:
        """Toggle selection for all actions."""
        toggle_all_logic(self, self.plan)

    def _refresh_node(self, node: Any) -> None:
        """Refresh the label and state of a single tree node."""
        refresh_node_logic(self, node)


class TextualPlanReviewer(IPlanReviewer):
    """
    Implements IPlanReviewer using the Textual TUI framework.
    """

    def __init__(
        self,
        system_env: ISystemEnvironment,
        file_system: IFileSystemManager,
        console_tooling: ConsoleToolingHelper,
        action_dispatcher: ActionDispatcher,
    ):
        self._system_env = system_env
        self._file_system = file_system
        self._console_tooling = console_tooling
        self._action_dispatcher = action_dispatcher

    def review(self, plan: Plan) -> Optional[Plan]:
        """
        Initiates the interactive review process using the Textual TUI.
        """
        return self._run_app(plan)

    def review_action(
        self,
        action: "ActionData",
        _total_actions: int,
        agent_name: Optional[str] = None,
    ) -> tuple[bool, str]:
        """
        For the TUI, per-action review is handled in bulk by review_plan.
        This method always returns True to allow the loop to proceed with selections.
        """
        _ = agent_name  # Mark as used for vulture
        return True, ""

    def _run_app(self, plan: Plan) -> Optional[Plan]:
        """
        Internal helper to launch the Textual app.
        Separated to allow for easier testing and mocking.
        """
        app = ReviewerApp(
            plan=plan,
            system_env=self._system_env,
            console_tooling=self._console_tooling,
            action_dispatcher=self._action_dispatcher,
            file_system=self._file_system,
        )
        result = app.run()
        if os.getenv("TEDDY_DEBUG") and result:
            print(
                f"\n[DEBUG] ReviewerApp.run() returned plan with {len(result.actions)} actions."
            )
        return result
