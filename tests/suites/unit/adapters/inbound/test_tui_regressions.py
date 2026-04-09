import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from textual.widgets import Label
from teddy_executor.core.domain.models.plan import Plan, ActionData
from teddy_executor.core.domain.models.execution_report import ActionLog, ActionStatus
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
    _update_detail_view,
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
    app = ReviewerApp(
        plan=Plan(title="T", rationale="R", actions=[action]),
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=MagicMock(),
        action_dispatcher=MagicMock(),
    )
    app.push_screen_wait = AsyncMock(return_value="q3 | q4")
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
                    await preview_readonly(app, action)
                    mock_suspend.assert_called_once()


@pytest.mark.anyio
async def test_regression_execution_log_removed(env):
    """Issue 5 & 7: Redundant execution log UI overlaps and freezes right panel on large output."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import DetailItem

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
        _update_detail_view(app, action)
        await pilot.pause()

        pane = app.query_one(ParameterDetail)
        labels = [str(label_widget.render()) for label_widget in pane.query(Label)]

        # Verify the legacy "LOG:" section is gone
        assert not any("LOG:" in label for label in labels)

        # Verify parameters are still rendered natively
        detail_items = list(pane.query(DetailItem))
        assert any(item.data.get("key") == "command" for item in detail_items)


@pytest.mark.anyio
@patch(
    "teddy_executor.adapters.inbound.textual_plan_reviewer_logic._update_detail_view"
)
async def test_regression_reactivity_on_edit(mock_update, env):
    """Issue 6: Editing a main action from the modal must immediately update the right pane."""
    action = ActionData(type="EXECUTE", params={"command": "ls"})
    app = ReviewerApp(
        plan=Plan(title="T", rationale="R", actions=[action]),
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=MagicMock(),
        action_dispatcher=MagicMock(),
    )
    app.push_screen_wait = AsyncMock(return_value="pwd")
    app._refresh_node = MagicMock()

    await edit_action_logic(app, MagicMock(), action)
    mock_update.assert_called_once_with(app, action)
