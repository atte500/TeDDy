from unittest.mock import Mock
from teddy_executor.core.domain.models.plan import Plan
from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer
from teddy_executor.adapters.inbound.textual_plan_reviewer import TextualPlanReviewer
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager


def test_textual_plan_reviewer_implements_protocol(container):
    """
    Verify that TextualPlanReviewer implements the IPlanReviewer protocol.
    """
    # Arrange
    reviewer = TextualPlanReviewer(
        system_env=container.resolve(ISystemEnvironment),
        file_system=container.resolve(IFileSystemManager),
    )

    # Assert
    assert isinstance(reviewer, IPlanReviewer)


def test_review_returns_plan_unchanged_in_non_interactive_mock(container, monkeypatch):
    """
    Verify the review entry point exists and returns a plan.
    (Note: This is a shallow test before we implement the actual App logic)
    """
    # Arrange
    reviewer = TextualPlanReviewer(
        system_env=container.resolve(ISystemEnvironment),
        file_system=container.resolve(IFileSystemManager),
    )
    plan = Plan(title="Test", rationale="Test", actions=[Mock(selected=True)])

    # Act
    # We'll mock the internal app.run() to avoid launching a TUI during unit tests
    monkeypatch.setattr(reviewer, "_run_app", lambda p: p)
    result = reviewer.review(plan)

    # Assert
    assert result == plan
