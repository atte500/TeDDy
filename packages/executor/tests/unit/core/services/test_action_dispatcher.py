from teddy_executor.core.domain.models import ActionData, ActionLog, ActionStatus
from teddy_executor.core.services.action_dispatcher import ActionDispatcher

# --- Test Doubles ---


class FakeSuccessfulAction:
    """A test double for a generic action that always succeeds."""

    def execute(self, **kwargs):
        return {"summary": "Fake action executed successfully."}


class FakeFailingAction:
    """A test double for a generic action that always fails."""

    def execute(self, **kwargs):
        raise RuntimeError("Fake action failed as intended.")


class FakeActionFactory:
    """A test double for the ActionFactory."""

    def __init__(self, actions_to_return: dict):
        self._actions = actions_to_return

    def create_action(self, action_type: str):
        return self._actions.get(action_type)


# --- Test Cases ---


def test_dispatch_and_execute_success():
    """
    Given a valid action that succeeds,
    When dispatch_and_execute is called,
    Then it should return a successful ActionLog.
    """
    # Arrange
    action_type = "fake_success_action"
    action_params = {"param1": "value1"}
    action_data = ActionData(type=action_type, params=action_params)

    fake_action = FakeSuccessfulAction()
    fake_factory = FakeActionFactory(actions_to_return={action_type: fake_action})

    dispatcher = ActionDispatcher(action_factory=fake_factory)

    # Act
    result_log = dispatcher.dispatch_and_execute(action_data)

    # Assert
    assert isinstance(result_log, ActionLog)
    assert result_log.status == ActionStatus.SUCCESS
    assert result_log.action_type == action_type
    assert result_log.params == action_params
    expected_details = {"summary": "Fake action executed successfully."}
    assert result_log.details == expected_details


def test_dispatch_and_execute_failure():
    """
    Given a valid action that fails by raising an exception,
    When dispatch_and_execute is called,
    Then it should return a failure ActionLog containing the exception details.
    """
    # Arrange
    action_type = "fake_failing_action"
    action_params = {"param1": "value1"}
    action_data = ActionData(type=action_type, params=action_params)

    fake_action = FakeFailingAction()
    fake_factory = FakeActionFactory(actions_to_return={action_type: fake_action})

    dispatcher = ActionDispatcher(action_factory=fake_factory)

    # Act
    result_log = dispatcher.dispatch_and_execute(action_data)

    # Assert
    assert isinstance(result_log, ActionLog)
    assert result_log.status == ActionStatus.FAILURE
    assert result_log.action_type == action_type
    assert result_log.params == action_params
    assert "Fake action failed as intended" in result_log.details
