import pytest
from unittest.mock import MagicMock
from teddy_executor.core.domain.models.plan import Plan, ActionData
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment


@pytest.mark.anyio
async def test_tui_create_action_save_as_workflow(env, monkeypatch):
    """
    Scenario: "Save As" workflow for CREATE actions.
    The system should launch the editor and prompt for a new path.
    """
    action = ActionData(
        type="CREATE",
        params={
            "path": "old/path.py",
            "content": "original content",
            "description": "desc",
        },
        selected=True,
    )
    plan = Plan(title="Save As Test", rationale="R", actions=[action])

    # Setup mocks
    sys_env = env.get_service(ISystemEnvironment)
    sys_env.create_temp_file.side_effect = lambda suffix=".txt": str(
        env.workspace / f"temp{suffix}"
    )
    # Mock editor output via environment variable (if supported by implementation)
    monkeypatch.setenv("TEDDY_TEST_MOCK_EDITOR_OUTPUT", "modified content")

    app = ReviewerApp(
        plan=plan,
        system_env=sys_env,
        file_system=env.get_mock_filesystem(),
        console_tooling=MagicMock(),
        action_dispatcher=MagicMock(),
    )

    async with app.run_test() as pilot:
        # 1. Highlight the CREATE action
        # Root (hidden) -> Rationale (down) -> Action Plan (down) -> Action 1 (down)
        await pilot.press("down", "down", "down")

        # 2. Edit path via right pane
        await pilot.press("tab")
        await pilot.press("enter")
        await pilot.pause()
        from textual.widgets import Input

        pilot.app.screen.query_one("#path_input", Input).value = "new/path.py"
        await pilot.press("enter")
        await pilot.pause()

        # 3. Edit content via tree key 'e'
        await pilot.press("shift+tab")
        await pilot.press("e")
        await pilot.wait_for_scheduled_animations()
        await pilot.press("y")

        # 5. Submit the plan
        await pilot.press("s")

    # Verification
    assert action.params["path"] == "new/path.py"
    assert action.params["content"] == "modified content"
    assert action.modified is True
