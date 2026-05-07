import pytest
from textual.app import App, ComposeResult
from textual.widgets import ListView, ListItem
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
    ParameterDetail,
    DetailItem,
)


@pytest.mark.anyio
async def test_reviewer_app_contains_parameter_detail_listview(container):
    """
    Assert that ReviewerApp uses ParameterDetail (ListView) instead of ParameterList (Tree).
    """
    from teddy_executor.core.domain.models.plan import ActionData, Plan

    action = ActionData(type="EXECUTE", params={"command": "ls"})
    plan = Plan(title="Test Plan", rationale="Test", actions=[action])
    from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
    from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper
    from teddy_executor.core.services.action_dispatcher import ActionDispatcher

    app = ReviewerApp(
        plan=plan,
        system_env=container.resolve(ISystemEnvironment),
        console_tooling=container.resolve(ConsoleToolingHelper),
        action_dispatcher=container.resolve(ActionDispatcher),
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        # Check for the new widget
        try:
            # Right pane is now a ContentSwitcher
            from textual.widgets import ContentSwitcher

            switcher = app.query_one("#right-pane")
            assert isinstance(switcher, ContentSwitcher)

            param_detail = app.query_one("#params-view")
            assert isinstance(param_detail, ParameterDetail), (
                "Right pane should contain a ParameterDetail widget"
            )
            assert isinstance(param_detail, ListView), (
                "ParameterDetail should be a ListView"
            )
        except Exception as e:
            pytest.fail(f"Could not find or validate ParameterDetail widget: {e}")


@pytest.mark.anyio
async def test_detail_item_contains_label_for_wrapping():
    """
    Assert that DetailItem is a ListItem containing a Label.
    """

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield DetailItem(key="path", val="/some/path")

    app = TestApp()
    async with app.run_test():
        item = app.query_one(DetailItem)
        assert isinstance(item, ListItem)

        from textual.widgets import Static

        label = item.query_one(Static)
        # In Textual, .render() returns the content for Static/Label widgets
        content = str(label.render())
        assert "path" in content.lower()
        assert "/some/path" in content
