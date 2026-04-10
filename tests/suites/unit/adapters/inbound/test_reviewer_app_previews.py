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
        await pilot.press("down", "down", "down")
        await pilot.press("e")
        # In ParameterEditModal, we type the new value and press enter
        await pilot.press(*"new")
        await pilot.press("enter")

    expected = ["new"] if action_type == "RESEARCH" else "new"
    assert action.params[param_key] == expected
    assert action.modified is True


@pytest.mark.anyio
async def test_reviewer_app_prompt_response_edit_routing(env):
    """Regression test ensuring PROMPT response edits route to user_response."""
    action = ActionData(type="PROMPT", params={"prompt": "Hello?"}, selected=True)
    plan = Plan(title="T", rationale="R", actions=[action])
    app = ReviewerApp(
        plan=plan,
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=MagicMock(),
        action_dispatcher=MagicMock(),
    )
    async with app.run_test() as pilot:
        # Highlight action in left tree
        await pilot.press("down", "down", "down")

        # Focus right pane ParameterDetail list
        await pilot.press("tab")
        # Go down to select the 'response' parameter item (Index 2: prompt, reference_files, response)
        await pilot.press("down", "down")
        # Trigger edit binding (which dynamically routes to right pane)
        await pilot.press("e")

        # Type the response in the modal
        await pilot.press(*"My Answer")
        await pilot.press("enter")

    # The 'response' key should NOT be injected into the params dictionary
    assert "response" not in action.params
    # Instead, it strictly sets the class attribute
    assert action.user_response == "My Answer"
    assert action.modified is True
