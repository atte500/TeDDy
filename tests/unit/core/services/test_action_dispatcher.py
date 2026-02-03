from unittest.mock import Mock
import pytest
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


# --- Fixtures ---


@pytest.fixture
def mock_action_factory() -> Mock:
    return Mock()


@pytest.fixture
def dispatcher(mock_action_factory: Mock) -> ActionDispatcher:
    return ActionDispatcher(action_factory=mock_action_factory)


# --- Test Cases ---


def test_dispatch_and_execute_success(
    dispatcher: ActionDispatcher, mock_action_factory: Mock
):
    """
    Given a valid action that succeeds,
    When dispatch_and_execute is called,
    Then it should return a successful ActionLog.
    """
    # Arrange
    action_type = "fake_success_action"
    action_params = {"param1": "value1"}
    action_data = ActionData(type=action_type, params=action_params)

    mock_action_factory.create_action.return_value = FakeSuccessfulAction()

    # Act
    result_log = dispatcher.dispatch_and_execute(action_data)

    # Assert
    assert isinstance(result_log, ActionLog)
    assert result_log.status == ActionStatus.SUCCESS
    assert result_log.action_type == action_type
    assert result_log.params == action_params
    expected_details = {"summary": "Fake action executed successfully."}
    assert result_log.details == expected_details


def test_dispatch_and_execute_failure(
    dispatcher: ActionDispatcher, mock_action_factory: Mock
):
    """
    Given a valid action that fails by raising an exception,
    When dispatch_and_execute is called,
    Then it should return a failure ActionLog containing the exception details.
    """
    # Arrange
    action_type = "fake_failing_action"
    action_params = {"param1": "value1"}
    action_data = ActionData(type=action_type, params=action_params)

    mock_action_factory.create_action.return_value = FakeFailingAction()

    # Act
    result_log = dispatcher.dispatch_and_execute(action_data)

    # Assert
    assert isinstance(result_log, ActionLog)
    assert result_log.status == ActionStatus.FAILURE
    assert result_log.action_type == action_type
    assert result_log.params == action_params
    assert isinstance(result_log.details, str)
    assert "Fake action failed as intended" in result_log.details
