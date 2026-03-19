from unittest.mock import Mock
import pytest
from teddy_executor.core.domain.models import ActionData
from teddy_executor.core.services.action_dispatcher import ActionDispatcher


@pytest.fixture
def dispatcher(container, mock_action_factory):
    return container.resolve(ActionDispatcher)


def test_dispatcher_normalizes_create_action_parameters(
    dispatcher, mock_action_factory
):
    """
    Given a CREATE action with 'file_path' parameter,
    When dispatch_and_execute is called,
    Then it should normalize 'file_path' to 'path' for the handler.
    """
    # Arrange
    action_data = ActionData(
        type="CREATE",
        params={"file_path": "foo.py", "content": "print('hi')"},
        description="Create foo",
    )

    mock_handler = Mock()
    mock_handler.execute.return_value = {"status": "success"}
    mock_action_factory.create_action.return_value = mock_handler

    # Act
    dispatcher.dispatch_and_execute(action_data)

    # Assert
    # Verify the factory received the normalized parameters
    args, kwargs = mock_action_factory.create_action.call_args
    assert args[0] == "CREATE"
    assert args[1]["path"] == "foo.py"
    assert "file_path" not in args[1]

    # Verify the handler received the normalized parameters
    handler_args, handler_kwargs = mock_handler.execute.call_args
    assert handler_kwargs["path"] == "foo.py"
    assert "file_path" not in handler_kwargs
