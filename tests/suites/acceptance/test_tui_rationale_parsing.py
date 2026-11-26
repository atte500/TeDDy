import pytest
from textual.widgets import ContentSwitcher
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import ActionTree
from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.core.services.action_dispatcher import ActionDispatcher
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.setup.rationale_scenarios import (
    NON_PROTOCOL_SECTIONS,
    PREAMBLE,
    rationale,
    section,
    sections,
)


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
async def test_tui_renders_every_authored_heading_as_a_node(env):
    """
    Verify every ### heading reaches the tree whether or not the plan format
    defines it, and that text before the first heading stays visible.
    """
    # GIVEN a rationale with a preamble plus headings the format does not define
    builder = MarkdownPlanBuilder("Authored Sections Test")
    builder.add_execute("ls")
    builder.with_rationale(
        rationale(
            PREAMBLE,
            section("Summary", "The summary."),
            sections(NON_PROTOCOL_SECTIONS),
        )
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

        assert titles == ["Untitled", "Summary", "Context", "Trade-offs"], (
            f"Expected every authored heading as a node, got {titles}"
        )

        # AND the non-protocol node carries only its own body
        context_node = rat_root.children[2]
        assert context_node.data["type"] == "RATIONALE_SECTION"
        assert context_node.data["title"] == "Context"
        assert context_node.data["content"] == "The context."


@pytest.mark.anyio
async def test_tui_renders_sectionless_rationale_as_untitled_node(env):
    """
    Verify a rationale carrying no heading becomes one `Untitled` node holding
    the whole content, and that selecting it shows that content.
    """
    # GIVEN a legacy rationale with no recognized ### heading
    builder = MarkdownPlanBuilder("Legacy Rationale Test")
    builder.add_execute("ls")
    builder.with_rationale(
        "1. Synthesis\nThe parser builds one plan per turn.\n\n"
        "2. Justification\nOne model call keeps the audit trail tight."
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

    # WHEN we open the plan reviewer on a sectionless rationale
    async with app.run_test() as pilot:
        # The rationale root is selected at mount, but its detail refresh is
        # deferred until after the first refresh, so wait for it before reading
        # the tree.
        await pilot.pause()
        tree = app.query_one(ActionTree)
        rat_root = tree.root.children[0]

        # THEN the root exposes a single Untitled node carrying the whole
        # rationale
        assert [child.label.plain for child in rat_root.children] == ["Untitled"]
        content = rat_root.children[0].data["content"]
        assert "1. Synthesis" in content
        assert "One model call keeps the audit trail tight." in content

        # AND selecting that node renders its content in the detail pane
        tree.move_cursor(rat_root.children[0])
        await pilot.pause()
        assert app.query_one(ContentSwitcher).current == "rationale-view"
