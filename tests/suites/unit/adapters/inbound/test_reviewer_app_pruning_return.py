import pytest
from unittest.mock import MagicMock
from teddy_executor.core.domain.models.plan import Plan, ActionData
from teddy_executor.core.domain.models.project_context import (
    ProjectContext,
    ContextItem,
)
from teddy_executor.adapters.inbound.textual_plan_reviewer_app import ReviewerApp
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment


@pytest.mark.anyio
async def test_reviewer_app_returns_pruned_context_metadata(env):
    # Arrange
    plan = Plan(
        title="Test Plan",
        rationale="Rationale",
        actions=[ActionData(type="READ", params={})],
    )

    items = [
        ContextItem(
            path="selected.py",
            token_count=100,
            git_status="",
            scope="Session",
            selected=True,
        ),
        ContextItem(
            path="pruned_1.py",
            token_count=200,
            git_status="M",
            scope="Turn",
            selected=False,
        ),
        ContextItem(
            path="pruned_2.py",
            token_count=300,
            git_status="??",
            scope="Turn",
            selected=False,
        ),
    ]
    context = ProjectContext(
        header="Header",
        content="Content",
        scoped_paths={
            "Session": ["selected.py"],
            "Turn": ["pruned_1.py", "pruned_2.py"],
        },
        items=items,
        agent_name="Architect",
        system_prompt_tokens=1000,
        total_window=128000,
    )

    app = ReviewerApp(
        plan=plan,
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=MagicMock(),
        action_dispatcher=MagicMock(),
        project_context=context,
    )

    # Act
    async with app.run_test() as pilot:
        # Simulate pressing 's' to submit
        await pilot.press("s")
        await pilot.wait_for_scheduled_animations()

    # Assert
    # ReviewerApp.exit(self.plan) makes the plan the return value of app.run()
    # In run_test, we check the app instance's plan directly if it's the same object
    assert "pruned_context" in plan.metadata
    assert plan.metadata["pruned_context"] == "pruned_1.py,pruned_2.py"


@pytest.mark.anyio
async def test_reviewer_app_no_pruned_context_if_all_selected(env):
    # Arrange
    plan = Plan(
        title="Test Plan",
        rationale="Rationale",
        actions=[ActionData(type="READ", params={})],
    )
    context = ProjectContext(
        header="H",
        content="C",
        items=[
            ContextItem(
                path="f.py", token_count=10, git_status="", scope="S", selected=True
            )
        ],
        scoped_paths={"S": ["f.py"]},
        agent_name="A",
        system_prompt_tokens=10,
        total_window=100,
    )
    app = ReviewerApp(
        plan=plan,
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=MagicMock(),
        action_dispatcher=MagicMock(),
        project_context=context,
    )

    # Act
    async with app.run_test() as pilot:
        await pilot.press("s")

    # Assert
    assert "pruned_context" not in plan.metadata
