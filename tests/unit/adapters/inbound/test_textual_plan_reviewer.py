from unittest.mock import Mock
from teddy_executor.core.domain.models.plan import Plan
from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer
from teddy_executor.adapters.inbound.textual_plan_reviewer import TextualPlanReviewer


def test_textual_plan_reviewer_implements_protocol():
    """
    Verify that TextualPlanReviewer implements the IPlanReviewer protocol.
    """
    # Arrange
    mock_system_env = Mock()
    mock_fs = Mock()
    reviewer = TextualPlanReviewer(system_env=mock_system_env, file_system=mock_fs)

    # Assert
    assert isinstance(reviewer, IPlanReviewer)


def test_review_returns_plan_unchanged_in_non_interactive_mock(monkeypatch):
    """
    Verify the review entry point exists and returns a plan.
    (Note: This is a shallow test before we implement the actual App logic)
    """
    # Arrange
    mock_system_env = Mock()
    mock_fs = Mock()
    reviewer = TextualPlanReviewer(system_env=mock_system_env, file_system=mock_fs)
    plan = Plan(title="Test", rationale="Test", actions=[Mock(selected=True)])

    # Act
    # We'll mock the internal app.run() to avoid launching a TUI during unit tests
    monkeypatch.setattr(reviewer, "_run_app", lambda p: p)
    result = reviewer.review(plan)

    # Assert
    assert result == plan
