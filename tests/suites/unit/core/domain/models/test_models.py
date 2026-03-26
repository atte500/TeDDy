from datetime import datetime
import pytest
from teddy_executor.core.domain.models import (
    ActionData,
    ExecutionReport,
    Plan,
    RunStatus,
    RunSummary,
)


def test_plan_can_hold_rationale():
    """Tests that the Plan model can store a rationale string."""
    actions = [
        ActionData(type="READ", params={"resource": "test.txt"}, description="test")
    ]
    plan = Plan(title="Test Plan", rationale="This is the rationale.", actions=actions)
    assert plan.rationale == "This is the rationale."


def test_execution_report_can_hold_rationale_and_original_actions():
    """Tests that the ExecutionReport can store rationale and original actions."""
    summary = RunSummary(
        status=RunStatus.SUCCESS, start_time=datetime.now(), end_time=datetime.now()
    )
    original_actions = [
        ActionData(type="READ", params={"resource": "test.txt"}, description="test")
    ]

    report = ExecutionReport(
        run_summary=summary,
        rationale="This is the rationale.",
        original_actions=original_actions,
        plan_title="Test Plan",
    )

    assert report.rationale == "This is the rationale."
    assert report.original_actions == original_actions


def test_execution_report_defaults_to_none_for_new_fields():
    """Ensures backward compatibility by defaulting new fields."""
    summary = RunSummary(
        status=RunStatus.SUCCESS, start_time=datetime.now(), end_time=datetime.now()
    )
    report = ExecutionReport(run_summary=summary)

    assert report.rationale is None
    assert report.original_actions == []


def test_plan_defaults_is_session_to_false():
    """Tests that a Plan defaults is_session to False."""
    actions = [
        ActionData(type="READ", params={"resource": "test.txt"}, description="test")
    ]
    plan = Plan(title="Test Plan", rationale="Rationale", actions=actions)
    assert plan.is_session is False


@pytest.mark.parametrize(
    "action_type, expected",
    [
        ("PROMPT", True),
        ("INVOKE", True),
        ("RETURN", True),
        ("CREATE", False),
        ("EDIT", False),
        ("EXECUTE", False),
        ("READ", False),
        ("PRUNE", False),
        ("RESEARCH", False),
    ],
)
def test_action_data_is_terminal(action_type, expected):
    """Tests that is_terminal property correctly identifies terminal actions."""
    action = ActionData(type=action_type, params={}, description="test")
    assert action.is_terminal is expected
