import pytest

from teddy_executor.core.domain.models import (
    ActionData,
    Plan,
    ExecutionReport,
    FileAlreadyExistsError,
    WebSearchError,
)


def test_plan_raises_error_on_empty_actions_list():
    """
    Tests that a Plan cannot be instantiated with an empty list of actions.
    """
    with pytest.raises(AssertionError, match="Plan must contain at least one action."):
        Plan(title="Test Plan", rationale="Test", actions=[])


def test_execution_report_instantiation():
    """
    Tests that an ExecutionReport can be instantiated with valid data.
    """
    from datetime import datetime
    from teddy_executor.core.domain.models import (
        RunSummary,
        ActionLog,
        RunStatus,
        ActionStatus,
    )

    summary = RunSummary(
        status=RunStatus.SUCCESS,
        start_time=datetime.now(),
        end_time=datetime.now(),
    )
    log = ActionLog(status=ActionStatus.SUCCESS, action_type="test", params={})
    report = ExecutionReport(run_summary=summary, action_logs=[log])

    assert report.run_summary.status == "SUCCESS"
    assert len(report.action_logs) == 1


def test_plan_instantiation():
    """
    Tests that a Plan can be instantiated with a list of actions.
    """
    actions = [ActionData(type="EXECUTE", params={"command": "ls"}, description="ls")]
    plan = Plan(title="Test Plan", rationale="Test", actions=actions)
    assert plan.actions == actions


def test_file_already_exists_error_stores_path():
    """
    Tests that the FileAlreadyExistsError custom exception correctly stores the file path.
    """
    path = "/path/to/some/file.txt"
    message = "File already exists"
    try:
        raise FileAlreadyExistsError(message, file_path=path)
    except FileAlreadyExistsError as e:
        assert str(e) == message
        assert e.file_path == path


def test_multiple_matches_found_error_can_be_raised_and_stores_content():
    """
    Tests that the MultipleMatchesFoundError custom exception can be raised
    and correctly stores the original content.
    """
    from teddy_executor.core.domain.models import MultipleMatchesFoundError

    original_content = "some original content"
    message = "Test error message"
    try:
        raise MultipleMatchesFoundError(message, content=original_content)
    except MultipleMatchesFoundError as e:
        assert str(e) == message
        assert e.content == original_content


def test_web_search_error_can_be_raised():
    """Tests that the WebSearchError can be raised and stores original exception."""
    original_exc = ValueError("Network failed")
    message = "Web search failed"
    try:
        raise WebSearchError(message, original_exception=original_exc)
    except WebSearchError as e:
        assert str(e) == message
        assert e.original_exception == original_exc
