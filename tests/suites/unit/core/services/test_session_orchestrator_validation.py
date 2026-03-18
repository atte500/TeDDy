import pytest
from unittest.mock import MagicMock

from teddy_executor.core.domain.models.plan import Plan, ActionData, ValidationError
from teddy_executor.core.services.session_orchestrator import SessionOrchestrator
from teddy_executor.core.services.session_replanner import SessionReplanner
from teddy_executor.core.ports.outbound import IFileSystemManager


@pytest.fixture
def mock_deps():
    return {
        "execution_orchestrator": MagicMock(),
        "session_service": MagicMock(),
        "file_system_manager": MagicMock(spec=IFileSystemManager),
        "report_formatter": MagicMock(),
        "plan_validator": MagicMock(),
        "planning_service": MagicMock(),
        "plan_parser": MagicMock(),
        "user_interactor": MagicMock(),
    }


def test_execute_triggers_replan_on_validation_failure(mock_deps):
    """
    SessionOrchestrator.execute should call the validator and, on failure,
    trigger the Automated Re-plan Loop.
    """
    # Given
    orchestrator = SessionOrchestrator(
        execution_orchestrator=mock_deps["execution_orchestrator"],
        session_service=mock_deps["session_service"],
        file_system_manager=mock_deps["file_system_manager"],
        report_formatter=mock_deps["report_formatter"],
        plan_validator=mock_deps["plan_validator"],
        planning_service=mock_deps["planning_service"],
        plan_parser=mock_deps["plan_parser"],
        user_interactor=mock_deps["user_interactor"],
        replanner=SessionReplanner(
            mock_deps["file_system_manager"], mock_deps["planning_service"]
        ),
        session_planner=MagicMock(),
    )

    plan = Plan(
        title="Faulty Plan",
        rationale="...",
        actions=[
            ActionData(
                type="EDIT", params={"path": "src/main.py"}, description="Faulty edit"
            )
        ],
    )
    mock_deps["plan_parser"].parse.return_value = plan

    # Mock validation failure
    errors = [ValidationError(message="Context error", file_path="src/main.py")]
    mock_deps["plan_validator"].validate.return_value = errors

    # Mock context resolution
    mock_deps["session_service"].resolve_context_paths.return_value = {
        "Session": [],
        "Turn": [],
    }
    mock_deps["planning_service"].generate_plan.return_value = ("02/plan.md", 0.0)

    plan_path = "01/plan.md"

    # When
    # We expect a specific behavior or a return value that indicates re-plan
    orchestrator.execute(plan_content="...", plan_path=plan_path)

    # Then
    # 1. Validator was called with context
    mock_deps["plan_validator"].validate.assert_called_once()

    # 2. transition_to_next_turn called with is_validation_failure=True and the failure report
    from unittest.mock import ANY

    mock_deps["session_service"].transition_to_next_turn.assert_called_with(
        plan_path=plan_path,
        execution_report=ANY,
        is_validation_failure=True,
        turn_cost=ANY,
    )

    # 3. planning_service.generate_plan was called for the next turn
    mock_deps["planning_service"].generate_plan.assert_called_once()


def test_execute_populates_failed_resources_on_validation_failure(mock_deps):
    """
    SessionOrchestrator should include the content of the failed file in the report.
    """
    # Given
    orchestrator = SessionOrchestrator(
        execution_orchestrator=mock_deps["execution_orchestrator"],
        session_service=mock_deps["session_service"],
        file_system_manager=mock_deps["file_system_manager"],
        report_formatter=mock_deps["report_formatter"],
        plan_validator=mock_deps["plan_validator"],
        planning_service=mock_deps["planning_service"],
        plan_parser=mock_deps["plan_parser"],
        user_interactor=mock_deps["user_interactor"],
        replanner=SessionReplanner(
            mock_deps["file_system_manager"], mock_deps["planning_service"]
        ),
        session_planner=MagicMock(),
    )

    plan = Plan(
        title="Faulty Plan",
        rationale="...",
        actions=[ActionData(type="EDIT", params={"path": "src/main.py"})],
    )
    mock_deps["plan_parser"].parse.return_value = plan

    # Mock validation failure with file_path
    errors = [ValidationError(message="Context error", file_path="src/main.py")]
    mock_deps["plan_validator"].validate.return_value = errors

    # Mock file system
    mock_deps["file_system_manager"].path_exists.return_value = True
    mock_deps["file_system_manager"].read_file.return_value = "original content"

    # When
    report = orchestrator.execute(plan_content="...", plan_path=None)

    # Then
    assert report.failed_resources == {"src/main.py": "original content"}
