import pytest
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser
from teddy_executor.core.domain.models import ActionType


def test_parser_handles_message_section():
    # Arrange
    builder = MarkdownPlanBuilder("Test Plan").with_agent("Pathfinder")
    builder.with_message(
        "This is a test message with **bold** text and [links](/path)."
    )
    plan_content = builder.build()
    parser = MarkdownPlanParser()

    # Act
    plan = parser.parse(plan_content)

    # Assert
    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.type == ActionType.MESSAGE
    assert (
        action.params["content"]
        == "This is a test message with **bold** text and [links](/path)."
    )


def test_parser_enforces_mutual_exclusivity():
    # Arrange
    builder = MarkdownPlanBuilder("Test Plan").add_read("/test")
    # Manually append the Message section to trigger exclusivity violation
    plan_content = builder.build() + "\n\n## Message\nIllegal message."
    parser = MarkdownPlanParser()

    # Act / Assert
    with pytest.raises(Exception) as excinfo:
        parser.parse(plan_content)

    assert "mutual exclusivity" in str(excinfo.value).lower()
