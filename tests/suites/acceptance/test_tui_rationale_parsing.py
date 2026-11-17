import pytest
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import ActionTree
from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.core.services.action_dispatcher import ActionDispatcher
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


@pytest.mark.anyio
async def test_tui_parses_default_rationale_sections(env):
    """
    Verify that the TUI exposes the default four-section rationale as nodes.
    """
    # GIVEN a plan built with the default rationale
    builder = MarkdownPlanBuilder("Robust Rationale Test")
    builder.add_execute("ls")
    plan_content = builder.build()

    parser = MarkdownPlanParser()
    plan = parser.parse(plan_content)

    app = ReviewerApp(
        plan=plan,
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=env.mock_port(ConsoleToolingHelper),
        action_dispatcher=env.mock_port(ActionDispatcher),
    )

    # WHEN we launch the TUI
    async with app.run_test():
        # THEN the Rationale tree exposes the four protocol sections
        tree = app.query_one(ActionTree)
        rat_root = tree.root.children[0]
        titles = [child.label.plain for child in rat_root.children]

        assert titles == ["Summary", "Expectation", "Progress", "Notes"], (
            f"Expected the four protocol sections, got {titles}"
        )


@pytest.mark.anyio
async def test_tui_parses_mixed_rationale_sections(env):
    """
    Verify that the TUI parses a rationale mixing legacy and protocol headings.
    """
    # GIVEN a plan whose rationale mixes a legacy numeric heading with ### headings
    builder = MarkdownPlanBuilder("Mixed Rationale Test")
    builder.add_execute("ls")
    builder.with_rationale(
        "1. Synthesis\nLegacy section content.\n\n"
        "### Expectation\nThe test should pass."
    )
    plan_content = builder.build()

    parser = MarkdownPlanParser()
    plan = parser.parse(plan_content)

    app = ReviewerApp(
        plan=plan,
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=env.mock_port(ConsoleToolingHelper),
        action_dispatcher=env.mock_port(ActionDispatcher),
    )

    async with app.run_test():
        tree = app.query_one(ActionTree)
        rat_root = tree.root.children[0]
        titles = [child.label.plain for child in rat_root.children]

        assert "Synthesis" in titles, f"Expected 'Synthesis' in {titles}"
        assert "Expectation" in titles, f"Expected 'Expectation' in {titles}"
