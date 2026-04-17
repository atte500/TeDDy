import pytest
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.drivers.tui_driver import TuiDriver


@pytest.mark.anyio
async def test_tui_swaps_to_markdown_view_for_rationale(env):
    test_env = env
    # Given a plan with a rationale section
    plan_content = (
        MarkdownPlanBuilder("Test Plan")
        .with_rationale("1. Synthesis\nThe logic is sound.")
        .add_create("file.txt", "content")
        .build()
    )
    from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
    from teddy_executor.core.ports.outbound import (
        ISystemEnvironment,
        IFileSystemManager,
    )

    plan = test_env.get_service(IPlanParser).parse(plan_content)
    driver = TuiDriver(
        plan,
        test_env.get_service(ISystemEnvironment),
        test_env.get_service(IFileSystemManager),
    )

    # When we navigate to the Rationale section in the TUI
    async with driver.app.run_test() as pilot:
        # 0. Focus the tree
        driver.app.query_one("#left-pane").focus()
        await pilot.pause()

        # 1. Move from Rationale root (expanded by default) to first child (Synthesis)
        await pilot.press("down")
        await pilot.pause()

        # Assert the Frontier: Switcher should be on rationale-view
        assert driver.get_active_view_id(pilot) == "rationale-view"
        assert "The logic is sound." in driver.get_markdown_content(pilot)
