from unittest.mock import MagicMock
from teddy_executor.core.services.action_executor import ActionExecutor
from teddy_executor.core.domain.models import ActionData, ActionStatus


def test_handle_skipped_action_retains_description():
    # Setup dependencies
    dispatcher = MagicMock()
    interactor = MagicMock()
    fs = MagicMock()
    simulator = MagicMock()
    config = MagicMock()

    executor = ActionExecutor(dispatcher, interactor, fs, simulator, config)

    # Create an action with a specific description
    target_description = "Special Test Description"
    action = ActionData(
        type="EXECUTE", params={"command": "echo hello"}, description=target_description
    )

    # Execute handle_skipped_action
    log = executor.handle_skipped_action(action, "Testing skip")

    # Assertions
    assert log.status == ActionStatus.SKIPPED
    assert log.action_type == "EXECUTE"
    # This is the core of the bug: 'Description' should be in the log's params
    assert "Description" in log.params, "Description was lost in ActionLog.params"
    assert log.params["Description"] == target_description
