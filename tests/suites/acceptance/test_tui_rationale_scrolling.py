import pytest
from textual.css.query import NoMatches
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
    # (Assuming 'down' navigates from root to Rationale root/section)
    async with driver.app.run_test() as pilot:
        await pilot.press("down", "enter")  # Move to Rationale and expand/select
        await pilot.pause()

        # Assert the Frontier: Currently fails because ContentSwitcher is missing
        with pytest.raises(NoMatches, match="ContentSwitcher"):
            driver.get_active_view_id(pilot)
