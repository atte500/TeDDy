import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from teddy_executor.core.domain.models.plan import (
    Plan,
    ActionData,
    ExecutionStatus,
)
from teddy_executor.core.domain.models.execution_report import ActionLog, ActionStatus
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
    edit_action_logic,
)
from teddy_executor.adapters.inbound.textual_plan_reviewer_previews import (
    preview_readonly,
)
from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
    resolve_action_parameters,
)
from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
    ParameterDetail,
)


@pytest.mark.anyio
async def test_regression_research_list_parsing(env):
    """Issue 2: RESEARCH modal expects a string but receives a list."""
    action = ActionData(type="RESEARCH", params={"queries": ["q1", "q2"]})
    app = MagicMock()
    app.push_screen_wait = AsyncMock(return_value="q3, q4")
    app._refresh_node = MagicMock()

    with patch(
        "teddy_executor.adapters.inbound.textual_plan_reviewer_logic._update_detail_view"
    ):
        await edit_action_logic(app, MagicMock(), action)

    assert action.params["queries"] == ["q3", "q4"]
    assert action.modified is True


def test_regression_prompt_parser_mapping():
    """Issue 3: PROMPT parameters are properly mapped to 'prompt' and user_response is preserved."""
    action = ActionData(type="PROMPT", params={"prompt": "Hello"})
    action.user_response = "World"
    resolved = resolve_action_parameters(action)

    assert resolved["prompt"] == "Hello"
    assert resolved["response"] == "World"
    assert "description" not in resolved


@pytest.mark.anyio
async def test_regression_read_action_suspend(env):
    """Issue 4: READ preview opens editor directly and deadlocks if app is not suspended."""
    action = ActionData(type="READ", params={"resource": "test.txt"})
    app = ReviewerApp(
        plan=Plan(title="T", rationale="R", actions=[action]),
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=MagicMock(),
        action_dispatcher=MagicMock(),
        file_system=MagicMock(),
    )
    app._system_env.create_temp_file = MagicMock(return_value="mock.txt")
    app._console_tooling.find_editor = MagicMock(return_value=["nano"])

    async with app.run_test():
        with patch.object(app, "suspend", MagicMock()) as mock_suspend:
            with patch("anyio.to_thread.run_sync", new_callable=AsyncMock):
                with patch("builtins.open", mock_open()):
                    with patch("os.chmod", MagicMock()):
                        await preview_readonly(app, action)
                    mock_suspend.assert_called_once()


@pytest.mark.anyio
async def test_regression_execution_log_removed(env):
    """Issue 5 & 7: Redundant execution log UI overlaps and freezes right panel on large output."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
        DetailItem,
        ActionTree,
    )

    action = ActionData(type="EXECUTE", params={"command": "ls"})
    action.executed = True
    action.action_log = ActionLog(
        action_type="EXECUTE",
        params={},
        status=ActionStatus.SUCCESS,
        details="Very long log output",
    )
    app = ReviewerApp(
        plan=Plan(title="T", rationale="R", actions=[action]),
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=MagicMock(),
        action_dispatcher=MagicMock(),
    )

    async with app.run_test() as pilot:
        # Settle initial mount logic
        await pilot.pause()

        # Find the node for our action to ensure the tree is correct
        tree = app.query_one(ActionTree)
        action_node = None
        for node in tree.root.children:
            if node.data == "ACTION_PLAN_ROOT":
                for leaf in node.children:
                    if leaf.data == action:
                        action_node = leaf
                        break
        assert action_node is not None

        # Ensure cursor is on action so our logic guard allows the update
        tree.move_cursor(action_node)

        # Directly invoke update logic for the action
        from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
            _update_detail_view,
        )

        _update_detail_view(app, action)

        # Give the ListView DOM time to process appends
        await pilot.pause()
        await pilot.pause()

        pane = app.query_one(ParameterDetail)
        from textual.widgets import Static

        labels = [str(label_widget.render()) for label_widget in pane.query(Static)]

        # Verify the legacy "LOG:" section is gone
        assert not any("LOG:" in label for label in labels)

        # Verify parameters are still rendered natively
        detail_items = list(pane.query(DetailItem))
        # After execution, 'command' is hidden; we verify 'status' instead
        assert any(item.data.get("key") == "status" for item in detail_items)


@pytest.mark.anyio
@patch(
    "teddy_executor.adapters.inbound.textual_plan_reviewer_logic._update_detail_view"
)
async def test_regression_reactivity_on_edit(mock_update, env):
    """Issue 6: Editing a main action from the modal must immediately update the right pane."""
    action = ActionData(type="EXECUTE", params={"command": "ls"})
    app = MagicMock()
    app.push_screen_wait = AsyncMock(return_value="pwd")
    app._refresh_node = MagicMock()

    await edit_action_logic(app, MagicMock(), action)
    mock_update.assert_called_once_with(app, action)


@pytest.mark.anyio
async def test_regression_orchestrate_execution_does_not_suspend_unnecessarily():
    """
    Ensures that orchestrate_execution does NOT suspend the TUI
    during non-interactive execution (which captures IO silently).
    """
    from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
        orchestrate_execution,
    )

    # Setup
    action = ActionData(type="EXECUTE", params={"command": "ls"}, selected=True)
    node = MagicMock()
    node.data = action

    mock_dispatcher = MagicMock()
    mock_dispatcher.dispatch_and_execute.return_value = ActionLog(
        status=ActionStatus.SUCCESS, action_type="EXECUTE", params={}
    )

    # Mock App
    app = MagicMock()
    app._action_dispatcher = mock_dispatcher
    app.is_headless = False

    # Execute
    await orchestrate_execution(app, node, lambda *_, **__: None)

    # Assert
    assert not app.suspend.called, (
        "app.suspend() should not be called for silent EXECUTE"
    )
    assert action.executed is True


@pytest.mark.anyio
async def test_regression_execute_prompt_step_populates_correct_log_details():
    """
    Regression test for Bug: PROMPT response missing from report.
    Ensures that manual PROMPT execution via TUI creates a dict-based log.
    """
    from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
        _execute_prompt_step,
    )

    # Setup
    app = MagicMock()
    app.INSTRUCTION_MARKER = "--- marker ---"
    action = ActionData(
        type="PROMPT", params={"prompt": "Confirm?"}, description="Test Prompt"
    )
    action.user_response = "Confirmed by user."
    action.modified = True  # Simulate user having edited the prompt in the editor

    node = MagicMock()
    node.data = action
    update_fn = MagicMock()

    # Mock preview_prompt to simulate completion
    with patch(
        "teddy_executor.adapters.inbound.textual_plan_reviewer_previews.preview_prompt"
    ):
        # Execute
        await _execute_prompt_step(app, action, node, update_fn)

        # Verify
        assert action.executed is True
        assert action.state == ExecutionStatus.SUCCESS
        assert isinstance(action.action_log.details, dict)
        assert action.action_log.details["response"] == "Confirmed by user."

        # Verify UI was refreshed
        app._refresh_node.assert_called_with(node)
        update_fn.assert_called_with(app, action)


@pytest.mark.anyio
async def test_regression_prompt_execution_does_not_suspend_unnecessarily():
    """
    Regression test for Bug: TUI Stutter on manual PROMPT execution.
    Ensures that prompt execution path does NOT suspend, as it relies on modals.
    """
    from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
        orchestrate_execution,
    )

    # Setup
    action = ActionData(type="PROMPT", params={"prompt": "Confirm?"})
    node = MagicMock()
    node.data = action
    update_fn = MagicMock()

    app = MagicMock()
    app.is_headless = False

    with patch(
        "teddy_executor.adapters.inbound.textual_plan_reviewer_helpers._execute_prompt_step",
        new_callable=AsyncMock,
    ):
        # Execute
        await orchestrate_execution(app, node, update_fn)

    # Assert
    assert not app.suspend.called, "app.suspend() should not be called for PROMPT"
