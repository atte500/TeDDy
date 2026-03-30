import pytest
import os
from teddy_executor.core.domain.models.plan import Plan, ActionData
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from tests.harness.drivers.tui_driver import TuiDriver


@pytest.mark.anyio
async def test_reviewer_app_marks_create_action_as_modified(container):
    # Arrange
    # We need a plan with one CREATE action
    action = ActionData(
        type="CREATE",
        params={"path": "test.py", "content": "original"},
        description="test",
        selected=True,
    )
    plan = Plan(title="Test", rationale="Test", actions=[action])

    system_env = container.resolve(ISystemEnvironment)
    file_system = container.resolve(IFileSystemManager)

    # Set mock editor output and debug
    os.environ["TEDDY_TEST_MOCK_EDITOR_OUTPUT"] = "modified content"
    os.environ["TEDDY_DEBUG"] = "true"

    try:
        driver = TuiDriver(plan, system_env, file_system)

        # Act: Navigate down to first child, then 'p' (preview)
        # Then handle PathInputScreen (enter) and ConfirmScreen (y)
        # Then 's' (submit)
        await driver.run_interaction(["down", "p", "enter", "y", "s"])

        # Assert
        assert action.modified is True
        assert action.params["content"] == "modified content"
    finally:
        if "TEDDY_TEST_MOCK_EDITOR_OUTPUT" in os.environ:
            del os.environ["TEDDY_TEST_MOCK_EDITOR_OUTPUT"]
