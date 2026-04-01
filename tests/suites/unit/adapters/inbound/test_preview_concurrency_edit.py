import pytest
import asyncio
from unittest.mock import MagicMock
from teddy_executor.core.domain.models.plan import Plan, ActionData
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import ConfirmScreen
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment


@pytest.mark.anyio
async def test_preview_edit_is_concurrent(env, monkeypatch):
    """
    Verify that preview_edit launches the editor and confirm prompt concurrently.
    """
    action = ActionData(
        type="EDIT",
        params={"path": "existing.py", "edits": [], "description": "d"},
        selected=True,
    )
    plan = Plan(title="T", rationale="R", actions=[action])

    # Mock launch_editor to be a slow task
    editor_event = asyncio.Event()

    async def slow_launch_editor(*_args, **_kwargs):
        await editor_event.wait()
        return "new content"

    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.textual_plan_reviewer_logic.launch_editor",
        slow_launch_editor,
    )

    app = ReviewerApp(
        plan=plan,
        system_env=MagicMock(spec=ISystemEnvironment),
        file_system=env.get_mock_filesystem(),
        console_tooling=MagicMock(),
    )
    # Ensure console_tooling.get_diff_viewer_command returns None to force launch_editor
    app._console_tooling.get_diff_viewer_command.return_value = None

    async with app.run_test() as pilot:
        await pilot.press("down")
        # Trigger edit
        asyncio.create_task(pilot.press("e"))
        await asyncio.sleep(0.1)  # Give it a moment to start

        # ASSERT: ConfirmScreen SHOULD be active while the editor is waiting
        assert isinstance(app.screen, ConfirmScreen)

        # Signal editor to finish
        editor_event.set()
        await asyncio.sleep(0.1)

        # Now ConfirmScreen should still be active, waiting for input
        assert isinstance(app.screen, ConfirmScreen)
        await pilot.press("y")

        # Now ConfirmScreen should be gone
        assert not isinstance(app.screen, ConfirmScreen)
