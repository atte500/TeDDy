from teddy_executor.core.domain.models import ActionData, ActionStatus
from teddy_executor.core.services.action_executor import ActionExecutor
from tests.harness.setup.test_environment import TestEnvironment


def test_action_executor_confirms_and_dispatches_with_real_dispatcher(monkeypatch):
    """
    Integration test ensuring ActionExecutor correctly coordinates with a
    fully-wired ActionDispatcher for a successful CREATE action.
    """
    # Arrange
    env = TestEnvironment(monkeypatch).setup()
    executor = env.get_service(ActionExecutor)

    # Mock user approval via harness
    env.get_mock_user_interactor().confirm_action.return_value = (True, "Approved")

    action = ActionData(
        type="CREATE",
        params={"path": "integration_test.txt", "content": "Hello Integration"},
        description="test action",
    )

    # Act
    log = executor.confirm_and_dispatch(action, interactive=True, total_actions=1)

    # Assert
    assert log.status == ActionStatus.SUCCESS

    # Verify the dispatcher actually wrote the file via the mock FS in the harness
    env.get_mock_filesystem().create_file.assert_called_once_with(
        path="integration_test.txt", content="Hello Integration"
    )
    env.get_mock_user_interactor().confirm_action.assert_called_once()
