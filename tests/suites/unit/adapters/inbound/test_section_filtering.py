from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
    ALLOWED_RATIONALE_SECTIONS,
)


def test_allowed_rationale_sections_contract():
    """Verify the white-list of rationale sections is correctly defined."""
    expected = [
        "Summary",
        "Expectation",
        "Progress",
        "Notes",
        "Synthesis",
        "Justification",
        "State Dashboard",
    ]
    assert ALLOWED_RATIONALE_SECTIONS == expected
