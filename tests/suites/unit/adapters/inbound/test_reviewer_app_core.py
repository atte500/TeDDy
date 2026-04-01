import pytest
from unittest.mock import MagicMock
from teddy_executor.core.domain.models.plan import Plan, ActionData, ExecutionStatus
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
    format_node_label,
)
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment


def test_format_node_label_with_execution_state():
    action = ActionData(type="EXECUTE", params={"command": "ls"}, selected=True)
    action.executed = True
    action.state = ExecutionStatus.SUCCESS
    label = format_node_label(action)
    assert "[green][SUCCESS]" in label
    assert "EXECUTE: ls" in label


@pytest.mark.anyio
async def test_reviewer_app_execute_key(env):
    action = ActionData(type="EXECUTE", params={"command": "ls"}, selected=True)
    plan = Plan(title="T", rationale="R", actions=[action])
    app = ReviewerApp(
        plan=plan,
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=MagicMock(),
    )
    async with app.run_test() as pilot:
        await pilot.press("down")
        await pilot.press("x")
        await pilot.wait_for_scheduled_animations()
        assert action.executed is True
        assert action.state == ExecutionStatus.SUCCESS
