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
    # Mock the refresh method to check if it's called
    app._refresh_node = MagicMock()

    async with app.run_test() as pilot:
        await pilot.press("down", "down", "down")
        await pilot.press("e")
        await pilot.pause()
        from textual.widgets import Input

        pilot.app.screen.query_one("#param_input", Input).value = "modified command"
        await pilot.press("enter")
        await pilot.pause()
    assert action.modified is True
    assert action.params["command"] == "modified command"

    # Assert that the UI was told to refresh
    app._refresh_node.assert_called_once()


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
        await pilot.press("down", "down", "down")
        assert app.check_action("revert", ()) is False
        action.modified = True
        await pilot.wait_for_scheduled_animations()
        assert app.check_action("revert", ()) is True
        await pilot.press("r")
        await pilot.wait_for_scheduled_animations()
    assert action.modified is False


@pytest.mark.anyio
async def test_reviewer_app_revert_restores_shallow_copy(env):
    """Regression test ensuring revert accurately restores original parsed lists."""
    action = ActionData(type="RESEARCH", params={"queries": ["original query"]})
    plan = Plan(title="T", rationale="R", actions=[action])
    app = ReviewerApp(
        plan=plan,
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=MagicMock(),
        action_dispatcher=MagicMock(),
    )
    async with app.run_test() as pilot:
        await pilot.press("down", "down", "down")

        # Simulate an edit mutation
        action.params["queries"] = ["mutated query"]
        action.modified = True

        # Trigger revert
        await pilot.press("r")
        await pilot.wait_for_scheduled_animations()

    assert action.modified is False
    assert action.params["queries"] == ["original query"]
