import pytest
from unittest.mock import MagicMock
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
        console_tooling=MagicMock(),
        action_dispatcher=MagicMock(),
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
        console_tooling=MagicMock(),
        action_dispatcher=MagicMock(),
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
