import pytest
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.inbound.planning_use_case import IPlanningUseCase
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.services.session_planner import SessionPlanner


@pytest.fixture
def mock_deps(env):
    return {
        "fs": env.mock_port(IFileSystemManager),
        "planning": env.mock_port(IPlanningUseCase),
        "interactor": env.mock_port(IUserInteractor),
        "session": env.mock_port(ISessionManager),
    }


@pytest.fixture
def planner(mock_deps):
    return SessionPlanner(
        file_system_manager=mock_deps["fs"],
        planning_service=mock_deps["planning"],
        user_interactor=mock_deps["interactor"],
        session_service=mock_deps["session"],
    )


def test_trigger_new_plan_delegates_to_planning_if_no_message_anywhere(
    planner, mock_deps
):
    # Arrange: No CLI message, no previous report
    turn_dir = "sessions/my-session/01"
    mock_deps["fs"].path_exists.return_value = False
    mock_deps["planning"].generate_plan.return_value = ("plan.md", 0.0)

    # Act
    planner.trigger_new_plan(turn_dir, message=None)

    # Assert
    # SessionPlanner now passes None to PlanningService, which will handle the prompt
    actual_message = mock_deps["planning"].generate_plan.call_args.kwargs[
        "user_message"
    ]
    assert actual_message is None


def test_trigger_new_plan_delegates_to_planning_if_report_request_section_is_empty(
    planner, mock_deps
):
    # Arrange: Report exists but 'User Request' section is empty
    turn_dir = "sessions/my-session/02"
    prev_report_path = "sessions/my-session/01/report.md"
    report_content = "# Report\n## User Request\n\n## Action Log\n..."

    mock_deps["fs"].path_exists.side_effect = lambda p: (
        p == prev_report_path or "meta.yaml" in p
    )
    mock_deps["fs"].read_file.side_effect = lambda p: (
        report_content if p == prev_report_path else "{}"
    )
    mock_deps["planning"].generate_plan.return_value = ("plan.md", 0.0)

    # Act
    planner.trigger_new_plan(turn_dir, message=None)

    # Assert
    # SessionPlanner found no message in report, so it passes None to PlanningService
    actual_message = mock_deps["planning"].generate_plan.call_args.kwargs[
        "user_message"
    ]
    assert actual_message is None


def test_trigger_new_plan_no_longer_displays_telemetry_directly(planner, mock_deps):
    """Migration: Telemetry is now handled by PlanningService."""
    # Arrange
    turn_dir = "sessions/my-session/01"
    mock_deps["fs"].path_exists.return_value = False
    mock_deps["planning"].generate_plan.return_value = ("plan.md", 0.05)

    # Act
    planner.trigger_new_plan(turn_dir, message=None)

    # Assert: Interactor should NOT have received telemetry calls
    # (Checking for 'Model' as it's a signature of the old telemetry display)
    telemetry_calls = [
        c
        for c in mock_deps["interactor"].display_message.call_args_list
        if "Model" in str(c)
    ]
    assert len(telemetry_calls) == 0, (
        f"SessionPlanner should not display telemetry. Found: {telemetry_calls}"
    )
