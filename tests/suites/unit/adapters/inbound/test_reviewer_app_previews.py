import pytest
from unittest.mock import MagicMock
from teddy_executor.core.domain.models.plan import Plan, ActionData
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment


@pytest.mark.anyio
@pytest.mark.parametrize(
    "action_type, param_key", [("EXECUTE", "command"), ("RESEARCH", "queries")]
)
async def test_reviewer_app_preview_text_actions(
    env, monkeypatch, action_type, param_key
):
    action = ActionData(
        type=action_type, params={param_key: "old", "description": "t"}, selected=True
    )
    plan = Plan(title="T", rationale="R", actions=[action])
    sys_env = env.get_service(ISystemEnvironment)
    monkeypatch.setenv("TEDDY_TEST_MOCK_EDITOR_OUTPUT", "new")
    app = ReviewerApp(
        plan=plan,
        system_env=sys_env,
        file_system=env.get_mock_filesystem(),
        console_tooling=MagicMock(),
        action_dispatcher=MagicMock(),
    )
    async with app.run_test() as pilot:
        await pilot.press("down")
        await pilot.press("e")
        # In ParameterEditModal, we type the new value and press enter
        await pilot.press(*"new")
        await pilot.press("enter")

    expected = ["new"] if action_type == "RESEARCH" else "new"
    assert action.params[param_key] == expected
    assert action.modified is True
