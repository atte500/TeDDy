from unittest.mock import ANY
from teddy_executor.core.domain.models.plan import Plan, ActionData, ValidationError
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase


def test_execute_triggers_replan_on_validation_failure(  # noqa: PLR0913
    container,
    mock_plan_parser,
    mock_plan_validator,
    mock_session_manager,
    mock_planning_service,
    mock_fs,
):
    """
    SessionOrchestrator.execute should call the validator and, on failure,
    trigger the Automated Re-plan Loop.
    """
    orchestrator = container.resolve(IRunPlanUseCase)

    plan = Plan(
        title="Faulty Plan",
        rationale="...",
        actions=[
            ActionData(
                type="EDIT", params={"path": "src/main.py"}, description="Faulty edit"
            )
        ],
    )
    mock_plan_parser.parse.return_value = plan

    # Mock validation failure
    errors = [ValidationError(message="Context error", file_path="src/main.py")]
    mock_plan_validator.validate.return_value = errors

    # Mock file system for report generation
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = "mock content"

    # Mock context resolution
    mock_session_manager.resolve_context_paths.return_value = {
        "Session": [],
        "Turn": [],
    }
    mock_planning_service.generate_plan.return_value = ("02/plan.md", 0.0)

    plan_path = "01/plan.md"

    # When
    orchestrator.execute(plan_content="...", plan_path=plan_path)

    # Then
    mock_plan_validator.validate.assert_called_once()
    mock_session_manager.transition_to_next_turn.assert_called_with(
        plan_path=plan_path,
        execution_report=ANY,
        is_validation_failure=True,
        turn_cost=ANY,
    )
    mock_planning_service.generate_plan.assert_called_once()


def test_execute_populates_failed_resources_on_validation_failure(
    container,
    mock_plan_parser,
    mock_plan_validator,
    mock_fs,
):
    """
    SessionOrchestrator should include the content of the failed file in the report.
    """
    orchestrator = container.resolve(IRunPlanUseCase)

    plan = Plan(
        title="Faulty Plan",
        rationale="...",
        actions=[ActionData(type="EDIT", params={"path": "src/main.py"})],
    )
    mock_plan_parser.parse.return_value = plan

    # Mock validation failure with file_path
    errors = [ValidationError(message="Context error", file_path="src/main.py")]
    mock_plan_validator.validate.return_value = errors

    # Mock file system
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = "original content"

    # When
    report = orchestrator.execute(plan_content="...", plan_path=None)

    # Then
    assert report.failed_resources == {"src/main.py": "original content"}
