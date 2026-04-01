import pytest
from unittest.mock import MagicMock
from teddy_executor.core.domain.models.plan import Plan, ActionData
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment


@pytest.mark.anyio
async def test_reviewer_app_prune_filtered_in_non_session(env):
    action = ActionData(type="PRUNE", params={"resource": "R"})
    plan = Plan(title="T", rationale="R", actions=[action], is_session=False)
    app = ReviewerApp(
        plan=plan,
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=MagicMock(),
    )
    async with app.run_test():
        from textual.widgets import Tree

        tree = app.query_one(Tree)
        assert len(tree.root.children) == 0
