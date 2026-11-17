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
async def test_tui_only_accepts_markdown_headings(env):
    """
    Verify only ### headings create nodes: a numeric marker is body text, and an
    unrecognized ### section merges into the previous node.
    """
    # GIVEN a rationale that uses a numeric marker and an unrecognized ### heading
    builder = MarkdownPlanBuilder("Marker Contract Test")
    builder.add_execute("ls")
    builder.with_rationale(
        "1. Synthesis\nA numeric marker is not a heading.\n\n"
        "### Summary\nThe summary.\n\n"
        "### Extra Details\nMerged into the summary node."
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

        assert titles == ["Summary"], f"Only ### headings create nodes, got {titles}"
        summary_node = rat_root.children[0]
        assert "The summary." in summary_node.data["content"]
        assert "Merged into the summary node." in summary_node.data["content"]
