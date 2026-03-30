import pytest
import os
from teddy_executor.core.domain.models.plan import Plan, ActionData
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from tests.harness.drivers.tui_driver import TuiDriver


@pytest.mark.anyio
async def test_reviewer_app_create_workflow_updates_path_and_content(container):
    """
    Tests that the CREATE workflow allows modifying both content and path,
    requiring a final confirmation.
    """
    # Arrange
    action = ActionData(
        type="CREATE",
        params={"path": "old.py", "content": "original"},
        description="test",
        selected=True,
    )
    plan = Plan(title="Test", rationale="Test", actions=[action])

    system_env = container.resolve(ISystemEnvironment)
    file_system = container.resolve(IFileSystemManager)

    # Set mock editor output
    os.environ["TEDDY_TEST_MOCK_EDITOR_OUTPUT"] = "new content"

    try:
        driver = TuiDriver(plan, system_env, file_system)

        # Act:
        # 1. down to action
        # 2. 'p' triggers preview (editor returns "new content")
        # 3. Path input appears (we type "new.py" and enter)
        # 4. Confirmation appears (we type "y")
        # 5. 's' to submit
        # Sequence:
        # 1. down to action
        # 2. 'p' triggers preview (editor returns "new content")
        # 3. PathInputScreen appears -> Type "new.py" + enter
        # 4. ConfirmScreen appears -> Press "y"
        # 5. Worker finishes -> Refresh node
        # 6. 's' to submit
        interaction = ["down", "p"]
        interaction.extend(list("new.py"))
        interaction.extend(["enter", "y", "s"])

        await driver.run_interaction(interaction)

        # Assert
        assert action.modified is True
        assert action.params["content"] == "new content"
        assert action.params["path"] == "new.py"
    finally:
        if "TEDDY_TEST_MOCK_EDITOR_OUTPUT" in os.environ:
            del os.environ["TEDDY_TEST_MOCK_EDITOR_OUTPUT"]
