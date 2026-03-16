import os
import pathlib
from typing import Any, Optional, TYPE_CHECKING
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Tree
from teddy_executor.core.domain.models.plan import Plan
from teddy_executor.core.services.edit_simulator import EditSimulator

if TYPE_CHECKING:
    from teddy_executor.core.domain.models.plan import ActionData

from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager


class ReviewerApp(App):
    """
    The Textual application for reviewing and modifying plans.
    """

    BINDINGS = [
        ("s", "submit", "Submit"),
        ("a", "toggle_all", "Toggle All"),
        ("p", "preview", "Preview/Modify"),
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

    def action_preview(self) -> None:
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
            self._preview_create(action, node)
        elif action.type == "EDIT":
            self._preview_edit(action, node)

    def _preview_edit(self, action: "ActionData", node: Any) -> None:
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
        temp_file = self._system_env.create_temp_file(suffix=suffix)
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(proposed_content)

        editor = (
            self._system_env.get_env("VISUAL")
            or self._system_env.get_env("EDITOR")
            or "nano"
        )
        with self.suspend():
            self._system_env.run_command([editor, temp_file])

        with open(temp_file, "r", encoding="utf-8") as f:
            final_content = f.read()

        # 4. If modified, override the action with a "content-override"
        if final_content != proposed_content:
            action.params["content"] = final_content
            action.modified = True
            self._refresh_node(node)

        self._system_env.delete_file(temp_file)

    def _preview_create(self, action: "ActionData", node: Any) -> None:
        """
        Handle the preview workflow for a CREATE action.
        """
        path_str = action.params.get("path", "")
        suffix = pathlib.Path(path_str).suffix or ".txt"

        temp_file = self._system_env.create_temp_file(suffix=suffix)
        content = action.params.get("content", "")

        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(content)

        editor = (
            self._system_env.get_env("VISUAL")
            or self._system_env.get_env("EDITOR")
            or "nano"
        )

        # Suspend the TUI and launch the editor
        with self.suspend():
            self._system_env.run_command([editor, temp_file])

        with open(temp_file, "r", encoding="utf-8") as f:
            new_content = f.read()

        if new_content != content:
            action.params["content"] = new_content
            action.modified = True
            self._refresh_node(node)

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
        Initiates the interactive review process.
        """
        return self._run_app(plan)

    def _run_app(self, plan: Plan) -> Optional[Plan]:
        """
        Internal helper to launch the Textual app.
        Separated to allow for easier testing and mocking.
        """
        app = ReviewerApp(
            plan=plan, system_env=self._system_env, file_system=self._file_system
        )
        return app.run()
