import pytest
from unittest.mock import MagicMock
from teddy_executor.core.domain.models.plan import Plan, ActionData
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.inbound.edit_simulator import IEditSimulator


@pytest.mark.anyio
async def test_tui_tracks_modified_field_on_parameter_edit(env):
    # Arrange
    action = ActionData(type="EXECUTE", params={"command": "ls -la"}, selected=True)
    plan = Plan(title="T", rationale="R", actions=[action])
    app = ReviewerApp(
        plan=plan,
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=MagicMock(),
        action_dispatcher=MagicMock(),
    )

    async with app.run_test() as pilot:
        # Navigate to Action and open editor (Assuming 'e' is bound to handle_edit_action for EXECUTE)
        await pilot.press("down", "down", "down")
        await pilot.press("e")
        await pilot.pause()

        from textual.widgets import Input

        pilot.app.screen.query_one("#param_input", Input).value = "modified command"
        await pilot.press("enter")
        await pilot.pause()

    # Assert
    assert action.modified is True
    assert "command" in action.modified_fields
    assert action.params["command"] == "modified command"


@pytest.mark.anyio
async def test_tui_clears_modified_fields_on_revert(env):
    # Arrange
    action = ActionData(
        type="EXECUTE",
        params={"command": "ls"},
        modified=True,
        modified_fields=["command"],
    )
    plan = Plan(title="T", rationale="R", actions=[action])
    app = ReviewerApp(
        plan=plan,
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=MagicMock(),
        action_dispatcher=MagicMock(),
    )

    async with app.run_test() as pilot:
        await pilot.press("down", "down", "down")
        # Trigger revert ('r')
        await pilot.press("r")
        await pilot.wait_for_scheduled_animations()

    # Assert
    assert action.modified is False
    assert len(action.modified_fields) == 0


@pytest.mark.anyio
async def test_tui_tracks_content_on_create_edit(env, monkeypatch):
    # Arrange
    action = ActionData(
        type="CREATE", params={"path": "new.txt", "content": "old"}, selected=True
    )
    plan = Plan(title="T", rationale="R", actions=[action])

    # Mock editor output
    monkeypatch.setenv("TEDDY_TEST_MOCK_EDITOR_OUTPUT", "new content")

    app = ReviewerApp(
        plan=plan,
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=MagicMock(),
        action_dispatcher=MagicMock(),
    )

    async with app.run_test() as pilot:
        await pilot.press("down", "down", "down")
        await pilot.press("e")
        await pilot.pause()

    # Assert
    assert action.modified is True
    assert "content" in action.modified_fields


@pytest.mark.anyio
async def test_tui_tracks_edits_on_edit_action(env, monkeypatch):
    # Arrange
    action = ActionData(
        type="EDIT", params={"path": "file.txt", "edits": []}, selected=True
    )
    plan = Plan(title="T", rationale="R", actions=[action])

    # Setup mock file system and editor
    fs = env.mock_port(IFileSystemManager)
    fs.read_file.return_value = "original"
    sim = env.mock_port(IEditSimulator)
    sim.simulate_edits.return_value = ("original", [])

    monkeypatch.setenv("TEDDY_TEST_MOCK_EDITOR_OUTPUT", "final")

    # Force use of launch_editor by making diff_viewer None
    console_tooling = MagicMock()
    console_tooling.get_diff_viewer_command.return_value = None

    app = ReviewerApp(
        plan=plan,
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=console_tooling,
        action_dispatcher=MagicMock(),
        file_system=fs,
    )
    # Manual injection since constructor doesn't support it
    app._edit_simulator = sim

    async with app.run_test() as pilot:
        await pilot.press("down", "down", "down")
        await pilot.press("e")
        await pilot.pause()

    # Assert
    assert action.modified is True
    assert "edits" in action.modified_fields


@pytest.mark.anyio
async def test_tui_tracks_user_response_on_prompt(env, monkeypatch):
    # Arrange
    action = ActionData(type="PROMPT", params={"prompt": "question"}, selected=True)
    plan = Plan(title="T", rationale="R", actions=[action])

    # Mock editor output (Instruction Bridge format)
    monkeypatch.setenv("TEDDY_TEST_MOCK_EDITOR_OUTPUT", "my response\n---\nquestion")

    app = ReviewerApp(
        plan=plan,
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=MagicMock(),
        action_dispatcher=MagicMock(),
    )

    async with app.run_test() as pilot:
        await pilot.press("down", "down", "down")
        await pilot.press("e")
        await pilot.pause()

    # Assert
    assert action.modified is True
    assert "user_response" in action.modified_fields
