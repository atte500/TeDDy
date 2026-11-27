import os
import tempfile
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import ActionTree
from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper
from teddy_executor.core.services.action_dispatcher import ActionDispatcher

from tests.harness.setup.mocking import spec_mock

if TYPE_CHECKING:
    from textual.pilot import Pilot

    from teddy_executor.core.domain.models.plan import Plan
    from teddy_executor.core.domain.models.project_context import ProjectContext


class TuiDriver:
    """
    Driver for the ReviewerApp (TUI) to support simulated interactions in tests.
    """

    def __init__(  # noqa: PLR0913 - forwards the app's injected port set
        self,
        plan: "Plan",
        system_env: Any,
        file_system: Any,
        console_tooling: Any = None,
        *,
        mock_editor_output: Optional[str] = None,
        action_dispatcher: Any = None,
        project_context: Optional["ProjectContext"] = None,
        agent_catalog: Any = None,
        session_manager: Any = None,
    ):
        self.editor_launch_suffixes: list[str] = []
        if mock_editor_output is not None:
            self._install_mock_editor(system_env, mock_editor_output)

        self.app = ReviewerApp(
            plan=plan,
            system_env=system_env,
            file_system=file_system,
            console_tooling=console_tooling or spec_mock(ConsoleToolingHelper),
            action_dispatcher=action_dispatcher or spec_mock(ActionDispatcher),
            project_context=project_context,
            agent_catalog=agent_catalog,
            session_manager=session_manager,
        )

    def _install_mock_editor(self, system_env: Any, output: str) -> None:
        """Routes every external-editor handover through the mock-editor hook.

        A handover asks `create_temp_file` for a path, so answering with a real
        file keeps the harvest path live, while the recorded suffix names the
        handover the editor branch requested. The replacement the hook writes is
        what the caller reads back, and a handover that never happens records
        nothing.
        """
        os.environ["TEDDY_TEST_MOCK_EDITOR_OUTPUT"] = output
        handover_dir = Path(tempfile.mkdtemp(prefix="teddy-tui-driver-"))
        create_temp_file = system_env.create_temp_file
        assert hasattr(create_temp_file, "side_effect"), (
            "mock_editor_output requires the harness ISystemEnvironment double, "
            "not a real adapter"
        )

        def _record_handover(suffix: str = "", **_port_options: Any) -> str:
            self.editor_launch_suffixes.append(suffix)
            path = handover_dir / f"handover-{len(self.editor_launch_suffixes)}{suffix}"
            path.touch()
            return str(path)

        create_temp_file.side_effect = _record_handover

    def tree(self, pilot: "Pilot") -> ActionTree:
        """Return the reviewer's action tree."""
        return pilot.app.query_one(ActionTree)

    def cursor_data(self, pilot: "Pilot") -> Any:
        """Return the payload of the node the cursor sits on."""
        node = self.tree(pilot).cursor_node
        return node.data if node is not None else None

    def find_node(self, pilot: "Pilot", matches: Callable[[Any], bool]) -> Any:
        """Return the first node in render order whose payload satisfies matches."""
        stack = [self.tree(pilot).root]
        while stack:
            node = stack.pop()
            if matches(node.data):
                return node
            stack.extend(reversed(node.children))
        raise AssertionError("no node in the tree matched the search")

    @asynccontextmanager
    async def interaction(self) -> AsyncIterator["Pilot"]:
        """Mount the app and hand back a pilot whose tree holds focus.

        Assertions about cursor position, focus, or scroll offset must run
        inside this block: the app is unmounted once it exits.
        """
        async with self.app.run_test() as pilot:
            self.tree(pilot).focus()
            await pilot.pause()
            yield pilot

    async def run_interaction(self, keys: Sequence[str]) -> Optional["Plan"]:
        """
        Runs the app and simulates the provided keypresses.
        """
        async with self.interaction() as pilot:
            for key in keys:
                await pilot.press(key)
                # If a worker is running (e.g. action_preview), we must not block
                # but we should allow it to reach its first await (e.g. push_screen_wait).
                await pilot.pause()

                # Optimization: Skip heavy worker synchronization for navigational keys
                # that do not trigger background processing.
                if key in ("up", "down", "left", "right", "tab"):
                    continue

                # If the current screen is a modal, wait for workers isn't
                # possible as they are blocked on the screen's dismissal.
                # Only wait for workers if we are on the main screen.
                if pilot.app.screen == pilot.app._screen_stack[0]:
                    await pilot.app.workers.wait_for_complete()
                    await pilot.pause()

            return self.app.plan

    async def set_input(self, pilot, selector: str, value: str):
        """
        Sets the value of an Input widget directly and submits it.
        This is significantly faster than pilot.press(*chars).
        """
        from textual.widgets import Input

        # Use app.screen to ensure we target the active (possibly modal) screen
        target = pilot.app.screen.query_one(selector, Input)
        target.value = value
        await pilot.press("enter")
        # Allow dismissal/callback processing
        await pilot.pause()

    def get_active_view_id(self, pilot) -> str:
        """Returns the current ID from the ContentSwitcher."""
        from textual.widgets import ContentSwitcher

        return pilot.app.query_one(ContentSwitcher).current

    def get_markdown_content(self, pilot) -> str:
        """Returns the text content of the Markdown widget."""
        # Use a more robust check for Markdown content in Textual
        from textual.widgets import Markdown

        widget = pilot.app.query_one(Markdown)
        # Try 'source' first as seen in dir(), then fallbacks
        for attr in ["source", "markup", "_markdown"]:
            val = getattr(widget, attr, None)
            if val:
                return str(val)
        return ""

    def get_param_value(self, pilot, key: str) -> str:
        """Returns the value the detail pane currently shows for a parameter."""
        from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
            ParameterDetail,
        )

        pane = pilot.app.query_one(ParameterDetail)
        for item in pane.children:
            data = getattr(item, "data", None)
            if isinstance(data, dict) and data.get("key") == key:
                return str(data["val"])
        raise AssertionError(f"No {key!r} parameter in the detail pane")
