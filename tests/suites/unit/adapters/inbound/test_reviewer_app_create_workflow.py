import pytest
from unittest.mock import MagicMock
from teddy_executor.core.domain.models.plan import Plan, ActionData
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment


@pytest.mark.anyio
async def test_reviewer_app_create_workflow(env, monkeypatch):
    action = ActionData(
        type="CREATE", params={"path": "old.py", "content": "old"}, selected=True
    )
    plan = Plan(title="T", rationale="R", actions=[action])
    sys_env = env.get_service(ISystemEnvironment)
    sys_env.create_temp_file.side_effect = lambda suffix=".txt": str(
        env.workspace / f"temp{suffix}"
    )
    monkeypatch.setenv("TEDDY_TEST_MOCK_EDITOR_OUTPUT", "new content")
    app = ReviewerApp(
        plan=plan,
        system_env=sys_env,
        file_system=env.get_mock_filesystem(),
        console_tooling=MagicMock(),
        action_dispatcher=MagicMock(),
    )
    async with app.run_test() as pilot:
        await pilot.press("down", "down", "down")
        # Edit path via right pane
        await pilot.press("tab")
        await pilot.press("enter")
        await pilot.pause()
        from textual.widgets import Input

        pilot.app.screen.query_one("#path_input", Input).value = "new.py"
        await pilot.press("enter")
        await pilot.pause()

        # Edit content via tree key 'e'
        await pilot.press("shift+tab")
        await pilot.press("e")
        await pilot.wait_for_scheduled_animations()
        await pilot.press("y")

        # Submit to harvest content
        await pilot.press("s")
    assert action.params["path"] == "new.py"
    assert action.params["content"] == "new content"
