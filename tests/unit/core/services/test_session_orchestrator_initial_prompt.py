from unittest.mock import MagicMock
import pytest
from teddy_executor.core.services.session_orchestrator import SessionOrchestrator
from teddy_executor.core.ports.outbound.session_manager import SessionState


@pytest.fixture
def mocks():
    return {
        "execution_orchestrator": MagicMock(),
        "session_service": MagicMock(),
        "file_system_manager": MagicMock(),
        "report_formatter": MagicMock(),
        "plan_validator": MagicMock(),
        "planning_service": MagicMock(),
        "plan_parser": MagicMock(),
        "user_interactor": MagicMock(),
    }


def test_trigger_new_plan_uses_ask_question(mocks):
    # Arrange
    orchestrator = SessionOrchestrator(**mocks)
    mocks["session_service"].get_session_state.return_value = (
        SessionState.EMPTY,
        "session/path",
    )
    mocks["user_interactor"].ask_question.return_value = "User instructions"

    # Act
    orchestrator.resume("session_name")

    # Assert
    # Should NOT use prompt
    mocks["user_interactor"].prompt.assert_not_called()
    # Should use ask_question
    mocks["user_interactor"].ask_question.assert_called_once_with(
        "Enter your instructions for the AI"
    )
    # Planning service should be called with the result
    mocks["planning_service"].generate_plan.assert_called_once()
    args = mocks["planning_service"].generate_plan.call_args.kwargs
    assert "User instructions" in args["user_message"]
