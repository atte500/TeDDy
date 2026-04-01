import pytest
from unittest.mock import MagicMock

from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment


@pytest.mark.anyio
async def test_tui_header_displays_plan_title_and_status(env):
    """
    Verify that the ReviewerApp header dynamically displays the plan's
    title and status emoji.
    """
    # Setup
    plan = Plan(
        title="Test Plan Title",
        rationale="Some rationale.",
        actions=[ActionData(type="CREATE", params={"path": "/dev/null"})],
        metadata={"Status": "Green 🟢"},
    )
    app = ReviewerApp(
        plan=plan,
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=MagicMock(),
    )

    # Driver & Observer
    async with app.run_test():
        assert app.title == "🟢 Test Plan Title"
