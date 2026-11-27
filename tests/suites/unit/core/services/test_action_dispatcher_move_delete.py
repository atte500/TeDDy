"""Contract tests for the MOVE and DELETE parameter translation seam."""

from teddy_executor.core.domain.models import ActionData, ActionStatus
from teddy_executor.core.services.action_dispatcher import ActionDispatcher
from teddy_executor.core.services.action_factory import ActionFactory


def test_dispatch_translates_move_source_and_destination(
    factory: ActionFactory, mock_fs
):
    """
    Given a parsed MOVE carrying the plan's vocabulary,
    When it is dispatched,
    Then the filesystem port receives its own `old_path`/`new_path` names.
    """
    # Arrange
    dispatcher = ActionDispatcher(action_factory=factory)
    action = ActionData(
        type="MOVE",
        params={"source": "app/old.py", "destination": "app/new.py"},
    )

    # Act
    action_log = dispatcher.dispatch_and_execute(action)

    # Assert
    assert action_log.status == ActionStatus.SUCCESS
    mock_fs.move_path.assert_called_once_with(
        old_path="app/old.py", new_path="app/new.py"
    )


def test_dispatch_forwards_delete_path_and_recursive(factory: ActionFactory, mock_fs):
    """
    Given a parsed DELETE,
    When it is dispatched,
    Then the port receives `path` and `recursive` unchanged.
    """
    # Arrange
    dispatcher = ActionDispatcher(action_factory=factory)
    action = ActionData(
        type="DELETE",
        params={"path": "app/legacy", "recursive": True},
    )

    # Act
    action_log = dispatcher.dispatch_and_execute(action)

    # Assert
    assert action_log.status == ActionStatus.SUCCESS
    mock_fs.remove_path.assert_called_once_with(path="app/legacy", recursive=True)
