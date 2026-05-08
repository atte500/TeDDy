import pytest
from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.drivers.tui_driver import TuiDriver
from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import ActionTree


def find_node_by_label_substring(tree: ActionTree, substring: str):
    """Helper to find a tree node by partial label match."""

    def _search(node):
        if substring in str(node.label):
            return node
        for child in node.children:
            result = _search(child)
            if result:
                return result
        return None

    return _search(tree.root)


@pytest.mark.anyio
async def test_session_context_node_visibility_and_formatting(env: TestEnvironment):
    # Arrange
    assert env.workspace is not None
    (env.workspace / "src").mkdir(parents=True)
    env.workspace.joinpath("src/logic.py").write_text("print('hello')")  # 14 chars

    from teddy_executor.core.ports.inbound.plan_parser import IPlanParser

    env.setup()

    plan_content = (
        MarkdownPlanBuilder("Test Wiring")
        .with_rationale("Verify context UI.")
        .add_create("out.txt", "content")
        .build()
    )
    # We parse the plan to get a Plan object for the TuiDriver
    plan = env.get_service(IPlanParser).parse(plan_content)

    # Mock project context with items
    from teddy_executor.core.domain.models.project_context import (
        ProjectContext,
        ContextItem,
    )

    items = [
        ContextItem(
            path="src/logic.py",
            token_count=140,
            git_status="M",
            scope="Turn",
            selected=True,
        )
    ]
    context = ProjectContext(
        header="Test Context",
        content="...",
        items=items,
        agent_name="Developer",
        system_prompt_tokens=1000,
        total_window=128000,
    )

    from teddy_executor.core.ports.outbound import (
        ISystemEnvironment,
        IFileSystemManager,
    )

    driver = TuiDriver(
        plan=plan,
        system_env=env.get_service(ISystemEnvironment),
        file_system=env.get_service(IFileSystemManager),
    )
    # Inject project context into the app
    driver.app.project_context = context

    # Act
    async with driver.app.run_test() as pilot:
        # Assert
        tree = pilot.app.query_one(ActionTree)

        # Verify "Context" root exists
        context_node = find_node_by_label_substring(tree, "Context")
        assert context_node is not None

        # Verify file item exists with formatting
        # Guideline: [bold]path[/] [[color]status[/]] [#888888]tokens[/]
        file_node = find_node_by_label_substring(tree, "src/logic.py")
        assert file_node is not None
        # Access .markup if label is a Rich Text object, otherwise use str()
        label_markup = getattr(file_node.label, "markup", str(file_node.label))
        assert "[bold]src/logic.py[/bold]" in label_markup
        assert "[[yellow]M[/yellow]]" in label_markup
        assert "[#888888]0.1k[/#888888]" in label_markup


@pytest.mark.anyio
async def test_auto_pruning_strikes_through_failed_plans(env: TestEnvironment):
    # Arrange
    from teddy_executor.core.ports.inbound.plan_parser import IPlanParser

    env.setup()

    plan_content = MarkdownPlanBuilder("Turn 2").add_read("README.md").build()
    plan = env.get_service(IPlanParser).parse(plan_content)

    from teddy_executor.core.domain.models.project_context import (
        ProjectContext,
        ContextItem,
    )

    items = [
        ContextItem(
            path="turn-01-plan.md",
            token_count=500,
            git_status="",
            scope="Turn",
            selected=False,
            auto_prune_reason="Pruned as it led to a non-green state",
        )
    ]
    context = ProjectContext(
        header="...",
        content="...",
        items=items,
        agent_name="Dev",
        system_prompt_tokens=0,
        total_window=0,
    )

    from teddy_executor.core.ports.outbound import (
        ISystemEnvironment,
        IFileSystemManager,
    )

    driver = TuiDriver(
        plan=plan,
        system_env=env.get_service(ISystemEnvironment),
        file_system=env.get_service(IFileSystemManager),
    )
    driver.app.project_context = context

    # Act
    async with driver.app.run_test() as pilot:
        # Assert
        tree = pilot.app.query_one(ActionTree)

        # Guideline: [s dim]path [[color]status[/]] tokens[/]
        # Note: Rich normalizes [s dim] to [dim strike]
        pruned_node = find_node_by_label_substring(tree, "turn-01-plan.md")
        assert pruned_node is not None
        label_markup = getattr(pruned_node.label, "markup", str(pruned_node.label))
        assert "[dim strike]" in label_markup
        assert "turn-01-plan.md" in label_markup
        assert "0.5k" in label_markup
