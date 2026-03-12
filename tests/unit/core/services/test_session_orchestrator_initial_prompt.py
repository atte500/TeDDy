from unittest.mock import MagicMock
import pytest
from teddy_executor.core.services.session_orchestrator import SessionOrchestrator
from teddy_executor.core.ports.outbound.session_manager import SessionState


@pytest.fixture
def mocks():
    fs = MagicMock()
    fs.read_file.return_value = (
        "agent_name: pathfinder\ncumulative_cost: 0.0\nturn_cost: 0.0"
    )

    ps = MagicMock()
    ps.generate_plan.return_value = "path/to/plan.md"

    ss = MagicMock()
    ss.get_session_state.return_value = (SessionState.EMPTY, "session/01")

    return {
        "execution_orchestrator": MagicMock(),
        "session_service": ss,
        "file_system_manager": fs,
        "report_formatter": MagicMock(),
        "plan_validator": MagicMock(),
        "planning_service": ps,
        "plan_parser": MagicMock(),
        "user_interactor": MagicMock(),
    }


def test_trigger_new_plan_uses_ask_question(mocks):
    # Arrange
    orchestrator = SessionOrchestrator(**mocks)

    # Mock valid plan to avoid re-plan loop in execute()
    from teddy_executor.core.domain.models.plan import Plan

    mock_plan = MagicMock(spec=Plan)
    mock_plan.title = "Test Plan"
    mock_plan.rationale = "Test Rationale"
    mocks["plan_parser"].parse.return_value = mock_plan
    mocks["plan_validator"].validate.return_value = []

    mocks["session_service"].get_session_state.side_effect = [
        (SessionState.EMPTY, "session/path"),
        (SessionState.PENDING_PLAN, "session/path"),
    ]
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
