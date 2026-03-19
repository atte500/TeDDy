from unittest.mock import MagicMock
import pytest
from teddy_executor.core.services.session_orchestrator import SessionOrchestrator
from teddy_executor.core.ports.outbound.session_manager import SessionState
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


@pytest.fixture
def orchestrator(  # noqa: PLR0913
    mock_run_plan,
    mock_session_manager,
    mock_fs,
    mock_report_formatter,
    mock_plan_validator,
    mock_planning_service,
    mock_plan_parser,
    mock_user_interactor,
    mock_context_service,
):
    from teddy_executor.core.services.session_planner import SessionPlanner
    from teddy_executor.core.services.session_replanner import SessionReplanner

    # Manual instantiation for unit tests ensures direct control over collaborators
    replanner = SessionReplanner(
        file_system_manager=mock_fs,
        planning_service=mock_planning_service,
    )
    session_planner = SessionPlanner(
        file_system_manager=mock_fs,
        planning_service=mock_planning_service,
        user_interactor=mock_user_interactor,
        session_service=mock_session_manager,
    )

    return SessionOrchestrator(
        execution_orchestrator=mock_run_plan,
        session_service=mock_session_manager,
        file_system_manager=mock_fs,
        report_formatter=mock_report_formatter,
        plan_validator=mock_plan_validator,
        planning_service=mock_planning_service,
        plan_parser=mock_plan_parser,
        user_interactor=mock_user_interactor,
        replanner=replanner,
        session_planner=session_planner,
    )


def _setup_mock_fs(mock_fs, plan_content):
    """Helper to configure mock_fs for session mode."""
    meta_content = "agent_name: pathfinder\nturn_cost: 0.0\ncumulative_cost: 0.0"

    def read_file_side_effect(path):
        if "meta.yaml" in str(path):
            return meta_content
        return plan_content

    mock_fs.read_file.side_effect = read_file_side_effect
    mock_fs.path_exists.return_value = True


def test_resume_triggers_execution_on_pending_plan(  # noqa: PLR0913
    orchestrator,
    mock_run_plan,
    mock_session_manager,
    mock_fs,
    mock_plan_parser,
    mock_plan_validator,
):
    """Scenario: Case B - PENDING_PLAN triggers execution."""
    session_name = "test-session"
    turn_path = ".teddy/sessions/test-session/01"
    plan_path = f"{turn_path}/plan.md"
    plan_content = MarkdownPlanBuilder("Test").build()

    mock_session_manager.get_session_state.return_value = (
        SessionState.PENDING_PLAN,
        turn_path,
    )
    _setup_mock_fs(mock_fs, plan_content)
    mock_plan_parser.parse.return_value = MagicMock(title="Test", rationale="Test")
    mock_plan_validator.validate.return_value = []

    orchestrator.resume(session_name, interactive=False)

    # SessionOrchestrator.execute should be called, which delegates to ExecutionOrchestrator
    mock_run_plan.execute.assert_called_once()
    args, kwargs = mock_run_plan.execute.call_args
    assert kwargs["plan_path"] == plan_path
    assert not kwargs["interactive"]


def test_resume_triggers_planning_on_empty_state(  # noqa: PLR0913
    orchestrator,
    mock_session_manager,
    mock_user_interactor,
    mock_planning_service,
    mock_plan_parser,
    mock_plan_validator,
    mock_fs,
):
    """Scenario: Case A - EMPTY triggers planning."""
    session_name = "test-session"
    turn_path = ".teddy/sessions/test-session/01"
    plan_content = MarkdownPlanBuilder("Test").build()

    # Mock valid plan to avoid re-plan loop in execute()
    from teddy_executor.core.domain.models.plan import Plan

    mock_plan = MagicMock(spec=Plan)
    mock_plan.title = "Test Plan"
    mock_plan.rationale = "Test Rationale"
    mock_plan_parser.parse.return_value = mock_plan
    mock_plan_validator.validate.return_value = []

    mock_session_manager.get_session_state.side_effect = [
        (SessionState.EMPTY, turn_path),
        (SessionState.PENDING_PLAN, turn_path),
    ]
    _setup_mock_fs(mock_fs, plan_content)
    mock_user_interactor.ask_question.return_value = "Initial task"
    mock_planning_service.generate_plan.return_value = (f"{turn_path}/plan.md", 0.0)

    orchestrator.resume(session_name)

    mock_planning_service.generate_plan.assert_called_once()
    args, kwargs = mock_planning_service.generate_plan.call_args
    assert "Initial task" in kwargs["user_message"]
    assert kwargs["turn_dir"] == turn_path


def test_resume_transitions_on_complete_turn(  # noqa: PLR0913
    orchestrator,
    mock_session_manager,
    mock_user_interactor,
    mock_planning_service,
    mock_plan_parser,
    mock_plan_validator,
    mock_fs,
):
    """Scenario: Case C - COMPLETE_TURN transitions then plans."""
    session_name = "test-session"
    turn_path = ".teddy/sessions/test-session/01"
    next_turn_path = ".teddy/sessions/test-session/02"
    plan_content = MarkdownPlanBuilder("Test").build()

    # Mock valid plan to avoid re-plan loop in execute()
    from teddy_executor.core.domain.models.plan import Plan

    mock_plan = MagicMock(spec=Plan)
    mock_plan.title = "Test Plan"
    mock_plan.rationale = "Test Rationale"
    mock_plan_parser.parse.return_value = mock_plan
    mock_plan_validator.validate.return_value = []

    mock_session_manager.get_session_state.side_effect = [
        (SessionState.COMPLETE_TURN, turn_path),
        (SessionState.PENDING_PLAN, next_turn_path),
    ]
    _setup_mock_fs(mock_fs, plan_content)
    mock_session_manager.transition_to_next_turn.return_value = next_turn_path
    mock_user_interactor.ask_question.return_value = "Next task"
    mock_planning_service.generate_plan.return_value = (
        f"{next_turn_path}/plan.md",
        0.0,
    )

    orchestrator.resume(session_name)

    # First transition: Triggered by resume() to move from COMPLETE_TURN to next EMPTY turn
    # Second transition: Triggered by execute() after the new plan is executed
    expected_transitions = 2
    assert (
        mock_session_manager.transition_to_next_turn.call_count == expected_transitions
    )
    mock_session_manager.transition_to_next_turn.assert_any_call(
        plan_path=f"{turn_path}/plan.md"
    )
    mock_planning_service.generate_plan.assert_called_once()
    args, kwargs = mock_planning_service.generate_plan.call_args
    assert "Next task" in kwargs["user_message"]
    assert kwargs["turn_dir"] == next_turn_path
