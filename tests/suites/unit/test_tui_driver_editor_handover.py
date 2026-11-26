import pytest
from textual.widgets import Tree

from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.ports.outbound import IFileSystemManager, ISystemEnvironment

from tests.harness.drivers.tui_driver import TuiDriver


def _build_driver(env, plan: Plan, mock_editor_output: str) -> TuiDriver:
    """Builds a driver that records external-editor handovers."""
    return TuiDriver(
        plan,
        env.get_service(ISystemEnvironment),
        env.get_service(IFileSystemManager),
        mock_editor_output=mock_editor_output,
    )


@pytest.mark.anyio
async def test_driver_feeds_replacement_through_editor_handover(env):
    """A recorded handover carries the injected replacement back into the plan."""
    plan = Plan(
        title="Test",
        rationale="Test",
        actions=[ActionData(type="MESSAGE", params={})],
    )
    driver = _build_driver(env, plan, mock_editor_output="My edited message")

    async with driver.app.run_test() as pilot:
        await pilot.press("m")
        await pilot.app.workers.wait_for_complete()
        await pilot.wait_for_scheduled_animations()

        await pilot.press("s")
        await pilot.app.workers.wait_for_complete()
        await pilot.wait_for_scheduled_animations()

    assert driver.editor_launch_suffixes == [".md"]
    assert plan.metadata.get("user_request") == "My edited message"


@pytest.mark.anyio
async def test_driver_exposes_parameter_value_without_editor_handover(env):
    """Highlighting a parameter records no handover and exposes its raw value."""
    plan = Plan(
        title="Test",
        rationale="Test",
        actions=[ActionData(type="EXECUTE", params={"command": "echo hi"})],
    )
    driver = _build_driver(env, plan, mock_editor_output="replaced")

    async with driver.app.run_test() as pilot:
        pilot.app.query_one(Tree).focus()
        await pilot.press("down", "down", "down")
        await pilot.pause()

        assert driver.get_param_value(pilot, "command") == "echo hi"
        assert driver.editor_launch_suffixes == []
