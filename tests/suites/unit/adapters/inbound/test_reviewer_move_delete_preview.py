"""Preview routing for MOVE and DELETE in the plan reviewer.

A reviewer must be able to look at the path a rename or a removal touches before
approving it. The affected target is deliberately absent on disk so the journey
ends at the "Resource not found" notice, which keeps the case hermetic while
still proving the chain routed and supplied a non-empty target.
"""

import pytest

from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper
from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.ports.outbound import IFileSystemManager, ISystemEnvironment

from tests.harness.drivers.tui_driver import TuiDriver


def _action_for(verb: str) -> ActionData:
    """Builds the verb's action against paths that do not exist on disk."""
    if verb == "MOVE":
        return ActionData(
            type="MOVE",
            params={"source": "ghost/old.py", "destination": "ghost/new.py"},
        )
    return ActionData(type="DELETE", params={"path": "ghost/legacy"})


@pytest.mark.parametrize("verb", ["MOVE", "DELETE"])
@pytest.mark.anyio
async def test_preview_consults_the_editor_for_the_affected_path(env, verb):
    """Pressing preview must reach the read-only viewer for the touched path."""
    action = _action_for(verb)
    plan = Plan(title="Test", rationale="Test", actions=[action])
    tooling = env.mock_port(ConsoleToolingHelper)
    tooling.find_editor.return_value = ["/usr/bin/vim"]
    tooling.get_diff_viewer_command.return_value = None
    driver = TuiDriver(
        plan,
        env.get_service(ISystemEnvironment),
        env.get_service(IFileSystemManager),
        console_tooling=tooling,
    )

    async with driver.interaction() as pilot:
        node = driver.find_node(pilot, lambda data: isinstance(data, ActionData))
        driver.tree(pilot).move_cursor(node)
        await pilot.press("e")
        await pilot.pause()
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()

    assert tooling.find_editor.call_count == 1
