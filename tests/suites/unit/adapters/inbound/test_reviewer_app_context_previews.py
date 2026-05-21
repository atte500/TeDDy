import pytest
from teddy_executor.core.domain.models.plan import Plan
from teddy_executor.core.domain.models.project_context import (
    ProjectContext,
    ContextItem,
)
from teddy_executor.adapters.inbound.textual_plan_reviewer_app import ReviewerApp
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
    ParameterDetail,
    ActionTree,
)
from teddy_executor.core.domain.models.plan import ActionData, ActionType


class StubConsoleTooling:
    pass


class StubActionDispatcher:
    pass


@pytest.mark.anyio
async def test_reviewer_app_shows_context_aggregate_detail(env):
    # Arrange
    ctx = ProjectContext(
        header="Test Header",
        content="Test Content",
        items=[
            ContextItem(
                path="src/core.py",
                token_count=1000,
                scope="Session",
                git_status="M",
                selected=True,
            ),
            ContextItem(
                path="tests/test_core.py",
                token_count=500,
                scope="Turn",
                git_status="??",
                selected=True,
            ),
        ],
        agent_name="Architect",
        system_prompt_tokens=2000,
        total_window=128000,
    )
    plan = Plan(
        title="T",
        rationale="R",
        actions=[ActionData(ActionType.READ, {"path": "dummy"})],
    )

    app = ReviewerApp(
        plan=plan,
        project_context=ctx,
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=StubConsoleTooling(),
        action_dispatcher=StubActionDispatcher(),
    )

    async with app.run_test() as pilot:
        # 1. Select Context Root (Initial focus)
        # Expected: Aggregate view with totals
        await pilot.pause()
        await pilot.pause()
        pane = app.query_one(ParameterDetail)
        content = "\n".join(str(getattr(child, "data", "")) for child in pane.children)

        assert "Total Context" in content
        assert "3.5k / 128k tokens" in content
        assert "• System" in content
        assert "2.0k" in content
        assert "• Session" in content
        assert "1.0k" in content
        assert "• Turn" in content
        assert "0.5k" in content


@pytest.mark.anyio
async def test_reviewer_app_renders_session_history_under_dedicated_node(env):
    # Arrange
    ctx = ProjectContext(
        header="Test Header",
        content="Test Content",
        items=[
            ContextItem(
                path=".teddy/sessions/20260521_134944-test-session/initial_request.md",
                token_count=1200,
                scope="Session",
                git_status=" ",
                selected=True,
            ),
            ContextItem(
                path=".teddy/sessions/20260521_134944-test-session/01/plan.md",
                token_count=4500,
                scope="Turn",
                git_status=" ",
                selected=True,
            ),
            ContextItem(
                path=".teddy/sessions/20260521_134944-test-session/01/report.md",
                token_count=3200,
                scope="Turn",
                git_status=" ",
                selected=True,
            ),
            ContextItem(
                path="src/main.py",
                token_count=2500,
                scope="Turn",
                git_status="M",
                selected=True,
            ),
        ],
        agent_name="Developer",
        system_prompt_tokens=1000,
        total_window=32000,
    )
    plan = Plan(
        title="Session History Test",
        rationale="Rationale",
        actions=[ActionData(ActionType.READ, {"path": "dummy"})],
    )

    app = ReviewerApp(
        plan=plan,
        project_context=ctx,
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=StubConsoleTooling(),
        action_dispatcher=StubActionDispatcher(),
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(ActionTree)

        # Retrieve the context root node (first child of tree root)
        context_root = tree.root.children[0]
        assert "Context" in str(context_root.label)

        # Map labels to their corresponding data identifiers
        children_labels = [str(c.label) for c in context_root.children]
        children_data = [c.data for c in context_root.children]

        # Verify that .teddy/sessions/ files do NOT appear in the generic Session: or Turn: lists
        from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
            SESSION_LABEL,
            TURN_LABEL,
            HISTORY_LABEL,
        )

        idx_session = children_data.index(SESSION_LABEL)
        idx_turn = children_data.index(TURN_LABEL)
        idx_history = children_data.index(HISTORY_LABEL)

        # Children under Session: (between Session: and Turn:)
        session_leaves = children_labels[idx_session + 1 : idx_turn]
        # Children under Turn: (between Turn: and History:)
        turn_leaves = children_labels[idx_turn + 1 : idx_history]
        # Children under History: (after History:)
        history_leaves = children_labels[idx_history + 1 :]

        # 1. Generic Session folder should only show (None) because the only session file was a history file
        assert len(session_leaves) == 1
        assert "(None)" in session_leaves[0]

        # 2. Generic Turn folder should only contain main.py
        assert len(turn_leaves) == 1
        assert "src/main.py" in turn_leaves[0]
        assert "plan.md" not in turn_leaves[0]
        assert "report.md" not in turn_leaves[0]

        # 3. History folder should be present and contain files chronologically with pretty names
        assert len(history_leaves) == 3
        assert "Initial Request" in history_leaves[0]
        assert "Turn 1: Plan" in history_leaves[1]
        assert "Turn 1: Execution Report" in history_leaves[2]


@pytest.mark.anyio
async def test_reviewer_app_shows_context_item_detail(env):
    # Arrange
    item = ContextItem(
        path="src/core.py",
        token_count=1200,
        scope="Session",
        git_status="M",
        selected=True,
        auto_prune_reason="Large file",
    )
    ctx = ProjectContext(
        header="H",
        content="C",
        items=[item],
        agent_name="A",
        system_prompt_tokens=0,
        total_window=0,
    )
    plan = Plan(
        title="T",
        rationale="R",
        actions=[ActionData(ActionType.READ, {"path": "dummy"})],
    )

    app = ReviewerApp(
        plan=plan,
        project_context=ctx,
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=StubConsoleTooling(),
        action_dispatcher=StubActionDispatcher(),
    )

    async with app.run_test() as pilot:
        # 1. Ensure Context Root is expanded and selected
        from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
            CONTEXT_ROOT,
        )

        tree = app.query_one(ActionTree)
        tree.jump_to_section(CONTEXT_ROOT)
        tree.focus()

        # 2. Move down to the first file item
        # Structure: Context Root -> System Header (1) -> Agent (2) -> Session Header (3) -> File (4)
        await pilot.press("down", "down", "down", "down")
        await pilot.pause()
        await pilot.pause()

        pane = app.query_one(ParameterDetail)
        content = "\n".join(str(getattr(child, "data", "")) for child in pane.children)

        assert "Path" in content
        assert "src/core.py" in content
        assert "Tokens" in content
        assert "1.2k" in content
        assert "Git Status" in content
        assert "Modified" in content
        assert "Scope" in content
        assert "Session" in content
        assert "Auto-Prune" in content
        assert "Large file" in content


@pytest.mark.anyio
async def test_reviewer_app_shows_history_row_in_context_aggregate_detail(env):
    # Arrange
    ctx = ProjectContext(
        header="Test Header",
        content="Test Content",
        items=[
            ContextItem(
                path=".teddy/sessions/20260521_134944-test-session/initial_request.md",
                token_count=1200,
                scope="Session",
                git_status=" ",
                selected=True,
            ),
            ContextItem(
                path=".teddy/sessions/20260521_134944-test-session/01/plan.md",
                token_count=4500,
                scope="Turn",
                git_status=" ",
                selected=True,
            ),
            ContextItem(
                path="src/main.py",
                token_count=2500,
                scope="Turn",
                git_status="M",
                selected=True,
            ),
        ],
        agent_name="Developer",
        system_prompt_tokens=1000,
        total_window=32000,
    )
    plan = Plan(
        title="Session History Aggregate Test",
        rationale="Rationale",
        actions=[ActionData(ActionType.READ, {"path": "dummy"})],
    )

    app = ReviewerApp(
        plan=plan,
        project_context=ctx,
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=StubConsoleTooling(),
        action_dispatcher=StubActionDispatcher(),
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        pane = app.query_one(ParameterDetail)
        content = "\n".join(str(getattr(child, "data", "")) for child in pane.children)

        assert "Total Context" in content
        assert "9.2k / 32k tokens" in content
        assert "• System" in content
        assert "1.0k" in content
        assert "• Session" in content
        assert "0.0k" in content  # history file excluded from Session total
        assert "• Turn" in content
        assert "2.5k" in content  # history file excluded from Turn total
        assert "• History" in content
        assert "5.7k" in content  # 1200 + 4500 = 5700 -> 5.7k
