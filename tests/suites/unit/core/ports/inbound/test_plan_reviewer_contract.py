from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer


def test_iplan_reviewer_defines_required_methods():
    """
    Verifies that IPlanReviewer Protocol defines the new required methods.
    """
    assert hasattr(IPlanReviewer, "review_plan"), (
        "IPlanReviewer must define review_plan"
    )
    assert hasattr(IPlanReviewer, "review_action"), (
        "IPlanReviewer must define review_action"
    )


def test_textual_plan_reviewer_implements_new_contract():
    """
    Verifies that the existing TextualPlanReviewer implementation is updated to the new contract.
    """
    from teddy_executor.adapters.inbound.textual_plan_reviewer import (
        TextualPlanReviewer,
    )
    from unittest.mock import MagicMock

    # We don't need real dependencies for a contract check
    reviewer = TextualPlanReviewer(system_env=MagicMock(), file_system=MagicMock())

    assert isinstance(reviewer, IPlanReviewer), (
        "TextualPlanReviewer must implement IPlanReviewer"
    )
    assert callable(getattr(reviewer, "review_plan")), (
        "TextualPlanReviewer must implement review_plan"
    )
    assert callable(getattr(reviewer, "review_action")), (
        "TextualPlanReviewer must implement review_action"
    )
