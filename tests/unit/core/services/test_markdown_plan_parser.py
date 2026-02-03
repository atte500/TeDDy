import pytest

from teddy_executor.core.domain.models import Plan
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser


@pytest.fixture
def parser() -> MarkdownPlanParser:
    return MarkdownPlanParser()


def test_parse_create_action(parser: MarkdownPlanParser):
    """
    Given a valid Markdown plan with a CREATE action,
    When the plan is parsed,
    Then a valid Plan domain object is returned with correct action data.
    """
    # Arrange
    plan_content = """
# Create a test file
- **Goal:** Create a simple file.

## Action Plan

### `CREATE`
- **File Path:** [hello.txt](/hello.txt)
- **Description:** Create a hello world file.
````text
Hello, world!
````
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    assert isinstance(result_plan, Plan)
    assert len(result_plan.actions) == 1
    action = result_plan.actions[0]

    assert action.type == "CREATE"
    assert action.description == "Create a hello world file."
    assert action.params == {
        "path": "/hello.txt",
        "content": "Hello, world!",
    }
