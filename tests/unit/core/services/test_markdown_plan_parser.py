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


def test_parse_read_action(parser: MarkdownPlanParser):
    """
    Given a valid Markdown plan with a READ action,
    When the plan is parsed,
    Then a valid Plan domain object is returned with correct action data.
    """
    # Arrange
    plan_content = """
# Read a file
- **Goal:** Read the architecture document.

## Action Plan

### `READ`
- **Resource:** [docs/ARCHITECTURE.md](/docs/ARCHITECTURE.md)
- **Description:** Read the current architectural conventions.
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    assert isinstance(result_plan, Plan)
    assert len(result_plan.actions) == 1
    action = result_plan.actions[0]

    assert action.type == "READ"
    assert action.description == "Read the current architectural conventions."
    assert action.params == {
        "resource": "/docs/ARCHITECTURE.md",
    }


def test_parse_edit_action(parser: MarkdownPlanParser):
    """
    Given a valid Markdown plan with a multi-block EDIT action,
    When the plan is parsed,
    Then a valid Plan domain object is returned with correct action data.
    """
    # Arrange
    plan_content = """
# Edit a file
- **Goal:** Update a class.

## Action Plan

### `EDIT`
- **File Path:** [src/my_class.py](/src/my_class.py)
- **Description:** Add a new method.

`FIND:`
````python
class MyClass:
    pass
````
`REPLACE:`
````python
class MyClass:
    def new_method(self):
        pass
````
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    assert isinstance(result_plan, Plan)
    assert len(result_plan.actions) == 1
    action = result_plan.actions[0]

    assert action.type == "EDIT"
    assert action.description == "Add a new method."
    assert action.params["path"] == "/src/my_class.py"
    assert len(action.params["edits"]) == 1
    assert action.params["edits"][0]["find"] == "class MyClass:\n    pass"
    assert (
        action.params["edits"][0]["replace"]
        == "class MyClass:\n    def new_method(self):\n        pass"
    )
