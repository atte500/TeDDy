"""
Regression test for Bug #17: MESSAGE action type under ## Action Plan
should produce a clear mutual exclusivity error instead of generic "Unknown action type: MESSAGE".
"""

import pytest
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser
from teddy_executor.core.ports.inbound.plan_parser import InvalidPlanError


def test_parser_raises_mutual_exclusivity_for_message_under_action_plan():
    """
    A plan containing `### MESSAGE` under `## Action Plan` should raise
    InvalidPlanError with a message explaining mutual exclusivity.
    """
    plan_content = (
        "# Test Plan\n"
        "- **Status:** Green 🟢\n"
        "- **Agent:** Debugger\n"
        "\n"
        "## Rationale\n"
        "~~~~~~\n"
        "Content\n"
        "~~~~~~\n"
        "\n"
        "## Action Plan\n"
        "\n"
        "### `MESSAGE`\n"
        "- **Description:** Test message\n"
        "~~~~~~\n"
        "Hello, this is a test message.\n"
        "~~~~~~\n"
    )

    parser = MarkdownPlanParser()
    with pytest.raises(InvalidPlanError) as excinfo:
        parser.parse(plan_content)

    error_msg = str(excinfo.value)
    assert "MESSAGE" in error_msg
    assert "mutual exclusivity" in error_msg.lower()
    assert "## Action Plan" in error_msg
