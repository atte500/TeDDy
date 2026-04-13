import pytest
from unittest.mock import MagicMock
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import ActionTree


@pytest.mark.anyio
async def test_tui_parses_numeric_rationale_sections(env):
    """
    Verify that the TUI can parse rationale sections formatted as '1. Section'.
    """
    # GIVEN a plan with numeric rationale sections
    builder = MarkdownPlanBuilder("Robust Rationale Test")
    builder.add_execute("ls")
    plan_content = builder.build()

    parser = MarkdownPlanParser()
    plan = parser.parse(plan_content)

    app = ReviewerApp(
        plan=plan,
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=MagicMock(),
        action_dispatcher=MagicMock(),
    )

    # WHEN we launch the TUI
    async with app.run_test():
        # THEN the Rationale tree should contain the numeric titles
        tree = app.query_one(ActionTree)
        # Find children of Rationale root (node at index 0)
        rat_root = tree.root.children[0]
        titles = [child.label.plain for child in rat_root.children]

        # Current logic will fail to parse these, so titles will be empty or wrong
        assert "Synthesis" in titles, f"Expected 'Synthesis' title in {titles}"
        assert "Justification" in titles, f"Expected 'Justification' title in {titles}"


@pytest.mark.anyio
async def test_tui_parses_mixed_rationale_sections(env):
    """
    Verify that the TUI can parse mixed rationale formats (### and 1.).
    """
    # GIVEN a plan with mixed rationale formats
    builder = MarkdownPlanBuilder("Mixed Rationale Test")
    builder.add_execute("ls")
    plan_content = builder.build()

    # Mix formats
    # builder.build() now produces "1. Synthesis" by default
    # We manually inject a legacy format to test MIXED capability
    plan_content = plan_content.replace("2. Justification", "### 2. Justification")

    parser = MarkdownPlanParser()
    plan = parser.parse(plan_content)

    app = ReviewerApp(
        plan=plan,
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=MagicMock(),
        action_dispatcher=MagicMock(),
    )

    async with app.run_test():
        tree = app.query_one(ActionTree)
        rat_root = tree.root.children[0]
        titles = [child.label.plain for child in rat_root.children]

        assert "Synthesis" in titles, f"Expected 'Synthesis' in {titles}"
        assert "Justification" in titles, f"Expected 'Justification' in {titles}"
