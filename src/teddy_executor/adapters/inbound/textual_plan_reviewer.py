import os
import pathlib
from typing import Any, Optional, TYPE_CHECKING
from textual import work
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Tree, Input, Label
from textual.screen import ModalScreen
from teddy_executor.core.domain.models.plan import Plan
from teddy_executor.core.services.edit_simulator import EditSimulator

if TYPE_CHECKING:
    from teddy_executor.core.domain.models.plan import ActionData

from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager


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


class ReviewerApp(App):
    """
    The Textual application for reviewing and modifying plans.
    """

    BINDINGS = [
        ("s", "submit", "Submit"),
        ("a", "toggle_all", "Toggle All"),
        ("p", "preview", "Preview/Modify"),
        ("v", "view_plan", "View Plan"),
        ("m", "add_message", "Add Message"),
        ("q", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        plan: Plan,
        system_env: ISystemEnvironment,
        file_system: Optional[IFileSystemManager] = None,
    ):
        super().__init__()
        self.plan = plan
        self._system_env = system_env
        self._file_system = file_system
        self._edit_simulator = EditSimulator()

    def compose(self) -> ComposeResult:
        """
        Create child widgets for the app.
        """
        yield Header()
        yield Tree("Action Plan")
        yield Footer()

    def on_mount(self) -> None:
        """
        Populate the action tree when the app is mounted.
        """
        if os.getenv("TEDDY_DEBUG"):
            self.log(f"Mounting ReviewerApp with {len(self.plan.actions)} actions.")

        tree = self.query_one(Tree)
        tree.root.expand()
        for action in self.plan.actions:
            if action.type == "PRUNE" and not self.plan.is_session:
                continue
            tree.root.add(self._format_node_label(action), data=action)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """
        Toggle action selection when a node is selected.
        """
        node = event.node
        action: Optional["ActionData"] = node.data

        if action is not None:
            action.selected = not action.selected
            self._refresh_node(node)

    def action_submit(self) -> None:
        """
        Exit the app and return the modified plan.
        """
        self.exit(self.plan)

    def action_cancel(self) -> None:
        """
        Exit the app and return None (cancellation).
        """
        self.exit(None)

    @work
    async def action_preview(self) -> None:
        """
        Preview and modify the currently selected action in an external editor.
        """
        tree = self.query_one(Tree)
        node = tree.cursor_node
        if not node:
            return

        action: Optional["ActionData"] = node.data
        if not action:
            return

        if action.type == "CREATE":
            await self._preview_create(action, node)
        elif action.type == "EDIT":
            await self._preview_edit(action, node)

    def action_view_plan(self) -> None:
        """
        Open the full plan.md in an external editor.
        """
        if not self.plan.plan_path or not self._file_system:
            return

        try:
            content = self._file_system.read_file(self.plan.plan_path)
            # Use launch_editor to handle TUI suspension and editor discovery
            self._launch_editor(content, suffix=".md")
        except Exception:  # nosec B110
            pass

    def action_add_message(self) -> None:
        """
        Open the external editor to add/edit the user instruction message.
        """
        current_message = self.plan.metadata.get("user_request") or ""
        new_message = self._launch_editor(current_message, suffix=".md")

        if new_message is not None and new_message.strip() != current_message.strip():
            self.plan.metadata["user_request"] = new_message.strip()

    async def _preview_edit(self, action: "ActionData", node: Any) -> None:
        """
        Handle the preview workflow for an EDIT action.
        """
        if not self._file_system:
            return

        path_str = action.params.get("path", "")
        suffix = pathlib.Path(path_str).suffix or ".txt"

        # 1. Read original content
        try:
            original_content = self._file_system.read_file(path_str)
        except Exception:
            original_content = ""

        # 2. Simulate the AI's proposed edits
        edits = action.params.get("edits", [])
        proposed_content, _ = self._edit_simulator.simulate_edits(
            original_content, edits
        )

        # 3. Open in editor
        final_content = self._launch_editor(proposed_content, suffix=suffix)
        if final_content is None:
            return

        # 4. Confirmation
        confirmed = await self.push_screen_wait(ConfirmScreen())
        if not confirmed:
            return

        # 5. If modified, override the action with a "content-override"
        if final_content != proposed_content:
            action.params["content"] = final_content
            action.modified = True
            self._refresh_node(node)

    async def _preview_create(self, action: "ActionData", node: Any) -> None:
        """
        Handle the preview workflow for a CREATE action.
        """
        path_str = action.params.get("path", "")
        suffix = pathlib.Path(path_str).suffix or ".txt"
        content = action.params.get("content", "")

        # 1. Content Edit
        new_content = self._launch_editor(content, suffix=suffix)
        if new_content is None:
            return

        # 2. Path Edit
        new_path = await self.push_screen_wait(PathInputScreen(path_str))
        if new_path is None:
            return

        # 3. Confirmation
        confirmed = await self.push_screen_wait(ConfirmScreen())
        if not confirmed:
            return

        # 4. Apply changes
        action.params["content"] = new_content
        action.params["path"] = new_path
        action.modified = True
        self._refresh_node(node)

    def _launch_editor(
        self, initial_content: str, suffix: str = ".txt"
    ) -> Optional[str]:
        """
        Suspends the TUI and launches an external editor with the given content.
        Returns the modified content, or None if the operation failed.
        """
        # Testing Hook
        mock_output = os.environ.get("TEDDY_TEST_MOCK_EDITOR_OUTPUT")
        if mock_output:
            return mock_output

        temp_file = self._system_env.create_temp_file(suffix=suffix)
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(initial_content)

            editor = (
                self._system_env.get_env("VISUAL")
                or self._system_env.get_env("EDITOR")
                or "nano"
            )

            with self.suspend():
                self._system_env.run_command([editor, temp_file])

            with open(temp_file, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return None
        finally:
            self._system_env.delete_file(temp_file)

    def action_toggle_all(self) -> None:
        """
        Toggle selection for all actions.
        """
        # Logic: if any is unselected, select all. Otherwise unselect all.
        any_unselected = any(not action.selected for action in self.plan.actions)
        new_state = any_unselected

        for action in self.plan.actions:
            action.selected = new_state

        # Refresh all child nodes in the tree
        tree = self.query_one(Tree)
        for node in tree.root.children:
            self._refresh_node(node)

    def _refresh_node(self, node: Any) -> None:
        """
        Refresh the label and state of a single tree node.
        """
        action: Optional["ActionData"] = node.data
        if action:
            node.label = self._format_node_label(action)

    def _format_node_label(self, action: "ActionData") -> str:
        """
        Format the label for a tree node based on action state.
        """
        prefix = "[✓]" if action.selected else "[ ]"
        label = f"{prefix} {action.type}: {self._get_action_summary(action)}"
        if action.modified:
            label += " *modified"
        return label

    def _get_action_summary(self, action: "ActionData") -> str:
        """
        Extract a concise summary for the action.
        """
        # Prioritize path-like parameters for a concise summary
        params = action.params
        return params.get("path") or params.get("resource") or params.get("command", "")


class TextualPlanReviewer(IPlanReviewer):
    """
    Implements IPlanReviewer using the Textual TUI framework.
    """

    def __init__(self, system_env: ISystemEnvironment, file_system: IFileSystemManager):
        self._system_env = system_env
        self._file_system = file_system

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
        return True, ""

    def _run_app(self, plan: Plan) -> Optional[Plan]:
        """
        Internal helper to launch the Textual app.
        Separated to allow for easier testing and mocking.
        """
        app = ReviewerApp(
            plan=plan, system_env=self._system_env, file_system=self._file_system
        )
        return app.run()
