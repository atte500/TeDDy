from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer


def test_iplan_reviewer_defines_required_methods():
    """
    Verifies that IPlanReviewer Protocol defines the required methods.
    """
    assert hasattr(IPlanReviewer, "review"), "IPlanReviewer must define review"
    assert hasattr(IPlanReviewer, "review_action"), (
        "IPlanReviewer must define review_action"
    )


def test_textual_plan_reviewer_implements_contract():
    """
    Verifies that the TextualPlanReviewer implementation adheres to the IPlanReviewer contract.
    """
    from teddy_executor.adapters.inbound.textual_plan_reviewer import (
        TextualPlanReviewer,
    )
    from unittest.mock import MagicMock

    # We don't need real dependencies for a contract check
    reviewer = TextualPlanReviewer(
        system_env=MagicMock(),
        file_system=MagicMock(),
        console_tooling=MagicMock(),
        action_dispatcher=MagicMock(),
    )

    assert isinstance(reviewer, IPlanReviewer), (
        "TextualPlanReviewer must implement IPlanReviewer"
    )
    assert callable(getattr(reviewer, "review")), (
        "TextualPlanReviewer must implement review"
    )
    assert callable(getattr(reviewer, "review_action")), (
        "TextualPlanReviewer must implement review_action"
    )
