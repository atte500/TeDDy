import pytest
from unittest.mock import MagicMock

from textual.widgets import Header
from textual.widgets._header import HeaderClock

from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment


@pytest.mark.anyio
async def test_tui_header_configuration(env):
    """
    Verify that the ReviewerApp header is correctly configured with
    the plan's title, status, and a clock.
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
        action_dispatcher=MagicMock(),
    )

    # Driver & Observer
    async with app.run_test():
        # Title and Status Emoji
        assert app.title == "🟢 Test Plan Title"

        # Clock Presence
        header = app.query_one(Header)
        # This will raise NoMatches if the clock widget is not found
        header.query_one(HeaderClock)
