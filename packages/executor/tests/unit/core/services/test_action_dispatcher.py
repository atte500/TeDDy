import json

from teddy_executor.core.domain.models import ActionData, V2_ActionLog
from teddy_executor.core.services.action_dispatcher import ActionDispatcher

# --- Test Doubles ---


class FakeSuccessfulAction:
    """A test double for a generic action that always succeeds."""

    def execute(self, **kwargs):
        return {"summary": "Fake action executed successfully."}


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
    assert isinstance(result_log, V2_ActionLog)
    assert result_log.status == "SUCCESS"
    assert result_log.action_type == action_type
    assert result_log.params == action_params
    expected_details = {"summary": "Fake action executed successfully."}
    assert result_log.details == json.dumps(expected_details)
