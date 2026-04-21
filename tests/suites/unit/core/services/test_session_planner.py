import pytest
from unittest.mock import MagicMock
from teddy_executor.core.services.session_planner import SessionPlanner


@pytest.fixture
def mock_deps():
    return {
        "fs": MagicMock(),
        "planning": MagicMock(),
        "interactor": MagicMock(),
        "session": MagicMock(),
    }


@pytest.fixture
def planner(mock_deps):
    return SessionPlanner(
        file_system_manager=mock_deps["fs"],
        planning_service=mock_deps["planning"],
        user_interactor=mock_deps["interactor"],
        session_service=mock_deps["session"],
    )


def test_trigger_new_plan_resolves_message_from_previous_report(planner, mock_deps):
    # Arrange: No CLI message provided, but previous report exists with a 'User Request'
    turn_dir = "sessions/my-session/02"
    prev_report_path = "sessions/my-session/01/report.md"

    report_content = """# Report
## User Request
Please fix the bug.
## Action Log
..."""

    mock_deps["fs"].path_exists.side_effect = lambda p: (
        p == prev_report_path or "meta.yaml" in p
    )
    mock_deps["fs"].read_file.side_effect = lambda p: (
        report_content if p == prev_report_path else "{}"
    )
    mock_deps["planning"].generate_plan.return_value = (
        "sessions/my-session/02/plan.md",
        0.05,
    )

    # Act
    planner.trigger_new_plan(turn_dir, message=None)

    # Assert
    # 1. User interactor should NOT have been prompted
    mock_deps["interactor"].ask_question.assert_not_called()

    # 2. Planning service should have received the message from the report
    # Note: SessionPlanner currently appends a hint, so we check if the base message is there
    actual_message = mock_deps["planning"].generate_plan.call_args.kwargs[
        "user_message"
    ]
    assert "Please fix the bug." in actual_message


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


def test_display_planning_telemetry_styles(planner, mock_deps):
    """Scenario: Session Visibility & Natural Language (Blue/Magenta Telemetry)"""
    from unittest.mock import call
    import yaml

    mock_deps["fs"].read_file.return_value = yaml.dump(
        {"model": "gpt-4o", "token_count": 12400, "cumulative_cost": 0.02}
    )

    # Act
    planner._display_planning_telemetry("turn_dir", "plan.md", 0.01)

    # Assert: Blue keys/bullets, Magenta values
    expected_calls = [
        call("[blue]• Model:[/blue] [magenta]gpt-4o[/magenta]"),
        call("[blue]• Context:[/blue] [magenta]12.4k tokens[/magenta]"),
        call("[blue]• Session Cost:[/blue] [magenta]$0.0300[/magenta]\n"),
    ]
    mock_deps["interactor"].display_message.assert_has_calls(expected_calls)
