import pytest
from unittest.mock import MagicMock
from teddy_executor.core.domain.models.plan import Plan, ActionData
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment


@pytest.mark.anyio
async def test_reviewer_app_edit_execute_parameter(env):
    action = ActionData(type="EXECUTE", params={"command": "ls -la"}, selected=True)
    plan = Plan(title="T", rationale="R", actions=[action])
    app = ReviewerApp(
        plan=plan,
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=MagicMock(),
        action_dispatcher=MagicMock(),
    )
    async with app.run_test() as pilot:
        await pilot.press("down")
        await pilot.press("e")
        await pilot.wait_for_scheduled_animations()
        await pilot.press(*"modified command")
        await pilot.press("enter")
        await pilot.wait_for_scheduled_animations()
    assert action.modified is True
    assert action.params["command"] == "modified command"


@pytest.mark.anyio
async def test_reviewer_app_revert_binding_visibility(env):
    action = ActionData(type="EXECUTE", params={"command": "ls"}, modified=False)
    plan = Plan(title="T", rationale="R", actions=[action])
    app = ReviewerApp(
        plan=plan,
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=MagicMock(),
        action_dispatcher=MagicMock(),
    )
    async with app.run_test() as pilot:
        await pilot.press("down")
        assert app.check_action("revert", ()) is False
        action.modified = True
        await pilot.wait_for_scheduled_animations()
        assert app.check_action("revert", ()) is True
        await pilot.press("r")
        await pilot.wait_for_scheduled_animations()
    assert action.modified is False
