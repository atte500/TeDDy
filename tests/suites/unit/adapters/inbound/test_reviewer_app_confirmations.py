import pytest
from unittest.mock import MagicMock
from teddy_executor.core.domain.models.plan import Plan, ActionData
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment


@pytest.mark.anyio
async def test_reviewer_app_message_deferral_and_stripping(env, monkeypatch):
    plan = Plan(title="T", rationale="R", actions=[ActionData(type="READ", params={})])
    app = ReviewerApp(
        plan=plan,
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=MagicMock(),
        action_dispatcher=MagicMock(),
    )
    marker = "\n\n<!-- Please enter your response above this line. -->"
    mock_content = f"Real user message{marker}\nStrip this."
    monkeypatch.setenv("TEDDY_TEST_MOCK_EDITOR_OUTPUT", mock_content)
    async with app.run_test() as pilot:
        await pilot.press("m")
        await pilot.wait_for_scheduled_animations()
        await pilot.press("y")
        await pilot.wait_for_scheduled_animations()
        assert plan.metadata.get("user_request") != "Real user message"
        await pilot.press("s")
        await pilot.wait_for_scheduled_animations()
    assert plan.metadata["user_request"] == "Real user message"
