import pytest
from unittest.mock import MagicMock
from teddy_executor.core.services.session_orchestrator import SessionOrchestrator
from teddy_executor.core.services.session_planner import SessionPlanner
from teddy_executor.core.services.session_replanner import SessionReplanner
from teddy_executor.core.ports.outbound.session_manager import SessionState


@pytest.fixture
def execution_orchestrator():
    return MagicMock()


@pytest.fixture
def session_service():
    return MagicMock()


@pytest.fixture
def file_system_manager():
    return MagicMock()


@pytest.fixture
def report_formatter():
    return MagicMock()


@pytest.fixture
def plan_validator():
    return MagicMock()


@pytest.fixture
def planning_service():
    return MagicMock()


@pytest.fixture
def plan_parser():
    return MagicMock()


@pytest.fixture
def user_interactor():
    return MagicMock()


@pytest.fixture
def orchestrator(  # noqa: PLR0913
    execution_orchestrator,
    session_service,
    file_system_manager,
    report_formatter,
    plan_validator,
    planning_service,
    plan_parser,
    user_interactor,
):
    return SessionOrchestrator(
        execution_orchestrator=execution_orchestrator,
        session_service=session_service,
        file_system_manager=file_system_manager,
        report_formatter=report_formatter,
        plan_validator=plan_validator,
        planning_service=planning_service,
        plan_parser=plan_parser,
        user_interactor=user_interactor,
        replanner=SessionReplanner(file_system_manager, planning_service),
        session_planner=SessionPlanner(
            file_system_manager, planning_service, user_interactor, session_service
        ),
    )


def test_resume_triggers_execution_on_pending_plan(  # noqa: PLR0913
    orchestrator,
    session_service,
    execution_orchestrator,
    file_system_manager,
    plan_parser,
    plan_validator,
):
    """Scenario: Case B - PENDING_PLAN triggers execution."""
    session_name = "test-session"
    turn_path = ".teddy/sessions/test-session/01"
    plan_path = f"{turn_path}/plan.md"

    session_service.get_session_state.return_value = (
        SessionState.PENDING_PLAN,
        turn_path,
    )
    file_system_manager.read_file.return_value = "# Plan"
    plan_parser.parse.return_value = MagicMock(title="Test", rationale="Test")
    plan_validator.validate.return_value = []  # No errors

    orchestrator.resume(session_name, interactive=False)

    # SessionOrchestrator.execute should be called, which delegates to execution_orchestrator
    execution_orchestrator.execute.assert_called_once()
    args, kwargs = execution_orchestrator.execute.call_args
    assert kwargs["plan_path"] == plan_path
    assert not kwargs["interactive"]


def test_resume_triggers_planning_on_empty_state(  # noqa: PLR0913
    orchestrator,
    session_service,
    user_interactor,
    planning_service,
    plan_parser,
    plan_validator,
):
    """Scenario: Case A - EMPTY triggers planning."""
    session_name = "test-session"
    turn_path = ".teddy/sessions/test-session/01"

    # Mock valid plan to avoid re-plan loop in execute()
    from teddy_executor.core.domain.models.plan import Plan

    mock_plan = MagicMock(spec=Plan)
    mock_plan.title = "Test Plan"
    mock_plan.rationale = "Test Rationale"
    plan_parser.parse.return_value = mock_plan
    plan_validator.validate.return_value = []

    session_service.get_session_state.side_effect = [
        (SessionState.EMPTY, turn_path),
        (SessionState.PENDING_PLAN, turn_path),
    ]
    user_interactor.ask_question.return_value = "Initial task"
    planning_service.generate_plan.return_value = (f"{turn_path}/plan.md", 0.0)

    orchestrator.resume(session_name)

    planning_service.generate_plan.assert_called_once()
    args, kwargs = planning_service.generate_plan.call_args
    assert "Initial task" in kwargs["user_message"]
    assert kwargs["turn_dir"] == turn_path


def test_resume_transitions_on_complete_turn(  # noqa: PLR0913
    orchestrator,
    session_service,
    user_interactor,
    planning_service,
    plan_parser,
    plan_validator,
):
    """Scenario: Case C - COMPLETE_TURN transitions then plans."""
    session_name = "test-session"
    turn_path = ".teddy/sessions/test-session/01"
    next_turn_path = ".teddy/sessions/test-session/02"

    # Mock valid plan to avoid re-plan loop in execute()
    from teddy_executor.core.domain.models.plan import Plan

    mock_plan = MagicMock(spec=Plan)
    mock_plan.title = "Test Plan"
    mock_plan.rationale = "Test Rationale"
    plan_parser.parse.return_value = mock_plan
    plan_validator.validate.return_value = []

    session_service.get_session_state.side_effect = [
        (SessionState.COMPLETE_TURN, turn_path),
        (SessionState.PENDING_PLAN, next_turn_path),
    ]
    session_service.transition_to_next_turn.return_value = next_turn_path
    user_interactor.ask_question.return_value = "Next task"
    planning_service.generate_plan.return_value = (f"{next_turn_path}/plan.md", 0.0)

    orchestrator.resume(session_name)

    # First transition: Triggered by resume() to move from COMPLETE_TURN to next EMPTY turn
    # Second transition: Triggered by execute() after the new plan is executed
    expected_transitions = 2
    assert session_service.transition_to_next_turn.call_count == expected_transitions
    session_service.transition_to_next_turn.assert_any_call(
        plan_path=f"{turn_path}/plan.md"
    )
    planning_service.generate_plan.assert_called_once()
    args, kwargs = planning_service.generate_plan.call_args
    assert "Next task" in kwargs["user_message"]
    assert kwargs["turn_dir"] == next_turn_path
