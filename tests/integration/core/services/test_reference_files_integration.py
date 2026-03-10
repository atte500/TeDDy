from unittest.mock import MagicMock
from teddy_executor.core.domain.models import ActionData
from teddy_executor.core.ports.outbound import IUserInteractor
from teddy_executor.core.services.action_dispatcher import ActionDispatcher


def test_prompt_action_dispatch_integration(container):
    """
    Verifies that the ActionDispatcher correctly wires a PROMPT action
    with Reference Files through to the (mocked) UserInteractor.
    """
    # Arrange
    # Mock the interactor to avoid blocking on stdin
    mock_interactor = MagicMock(spec=IUserInteractor)
    mock_interactor.ask_question.return_value = "Mocked Response"
    container.register(IUserInteractor, instance=mock_interactor)

    dispatcher = container.resolve(ActionDispatcher)
    action_data = ActionData(
        type="PROMPT",
        params={"prompt": "Hello", "handoff_resources": ["ref.txt"]},
        description="Prompt with ref",
    )

    # Act
    log = dispatcher.dispatch_and_execute(action_data)

    # Assert
    assert log.status.value == "SUCCESS"
    # Verify that the interactor was called with the correct arguments
    mock_interactor.ask_question.assert_called_once_with("Hello", resources=["ref.txt"])
