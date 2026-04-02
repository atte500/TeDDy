import pytest
import asyncio
from unittest.mock import MagicMock
from teddy_executor.core.domain.models.plan import Plan, ActionData
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
    PathInputScreen,
)


@pytest.mark.anyio
async def test_preview_create_is_concurrent(env, monkeypatch):
    """
    Verify that preview_create launches the editor and path prompt concurrently.
    """
    action = ActionData(
        type="CREATE",
        params={"path": "old.py", "content": "old", "description": "d"},
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
        action_dispatcher=MagicMock(),
    )

    async with app.run_test() as pilot:
        await pilot.press("down")
        # Trigger edit
        asyncio.create_task(pilot.press("e"))
        await asyncio.sleep(0.1)  # Give it a moment to start

        # ASSERT: PathInputScreen SHOULD be active while the editor is waiting
        assert isinstance(app.screen, PathInputScreen)

        # Signal editor to finish
        editor_event.set()
        await asyncio.sleep(0.1)

        # Now handle the path input
        await pilot.press(*"new.py")
        await pilot.press("enter")

        # Now PathInputScreen should be gone (ConfirmScreen or main screen)
        assert not isinstance(app.screen, PathInputScreen)
