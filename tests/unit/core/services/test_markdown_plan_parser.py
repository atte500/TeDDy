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
        "path": "hello.txt",
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
        "resource": "docs/ARCHITECTURE.md",
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
    assert action.params["path"] == "src/my_class.py"
    assert len(action.params["edits"]) == 1
    assert action.params["edits"][0]["find"] == "class MyClass:\n    pass"
    assert (
        action.params["edits"][0]["replace"]
        == "class MyClass:\n    def new_method(self):\n        pass"
    )


def test_parse_execute_action(parser: MarkdownPlanParser):
    """
    Given a valid Markdown plan with an EXECUTE action,
    When the plan is parsed,
    Then a valid Plan domain object is returned with correct action data.
    """
    # Arrange
    plan_content = """
# Execute a command
- **Goal:** Run a test.

## Action Plan

### `EXECUTE`
- **Description:** Run the test suite.
- **Expected Outcome:** All tests will pass.
- **cwd:** /tmp/tests
- **env:**
    - `API_KEY`: "secret"
    - `DEBUG`: "1"
````shell
poetry run pytest
````
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    assert isinstance(result_plan, Plan)
    assert len(result_plan.actions) == 1
    action = result_plan.actions[0]

    assert action.type == "EXECUTE"
    assert action.description == "Run the test suite."
    assert action.params["command"] == "poetry run pytest"
    assert action.params["expected_outcome"] == "All tests will pass."
    assert action.params["cwd"] == "/tmp/tests"
    assert action.params["env"] == {"API_KEY": "secret", "DEBUG": "1"}


def test_parse_research_action(parser: MarkdownPlanParser):
    """
    Given a valid Markdown plan with a RESEARCH action with multiple queries,
    When the plan is parsed,
    Then a valid Plan domain object is returned with correct action data.
    """
    # Arrange
    plan_content = """
# Research a topic
- **Goal:** Find a library.

## Action Plan

### `RESEARCH`
- **Description:** Find libraries for parsing Markdown.
````text
python markdown ast library
````
````text
best python markdown parser
````
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    assert isinstance(result_plan, Plan)
    assert len(result_plan.actions) == 1
    action = result_plan.actions[0]

    assert action.type == "RESEARCH"
    assert action.description == "Find libraries for parsing Markdown."
    assert action.params["queries"] == [
        "python markdown ast library",
        "best python markdown parser",
    ]


def test_parse_chat_with_user_action(parser: MarkdownPlanParser):
    """
    Given a valid Markdown plan with a CHAT_WITH_USER action,
    When the plan is parsed,
    Then a valid Plan domain object is returned with correct action data.
    """
    # Arrange
    plan_content = r"""
# Chat with the user
- **Goal:** Get feedback.

## Action Plan

### `CHAT_WITH_USER`
This is the first paragraph of the prompt.

This is the second paragraph, with some `inline_code`.
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    assert isinstance(result_plan, Plan)
    assert len(result_plan.actions) == 1
    action = result_plan.actions[0]

    expected_prompt = (
        "This is the first paragraph of the prompt.\n\n"
        "This is the second paragraph, with some `inline_code`."
    )

    assert action.type == "CHAT_WITH_USER"
    assert action.description is None  # No description metadata for this action
    assert action.params["prompt"] == expected_prompt


def test_parse_prune_action(parser: MarkdownPlanParser):
    """
    Given a valid Markdown plan with a PRUNE action,
    When the plan is parsed,
    Then a valid Plan domain object is returned with correct action data.
    """
    # Arrange
    plan_content = """
# Prune a resource from context
- **Goal:** Clean up the context.

## Action Plan

### `PRUNE`
- **Resource:** [docs/specs/old-spec.md](/docs/specs/old-spec.md)
- **Description:** Remove the old specification.
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    assert isinstance(result_plan, Plan)
    assert len(result_plan.actions) == 1
    action = result_plan.actions[0]

    assert action.type == "PRUNE"
    assert action.description == "Remove the old specification."
    assert action.params == {
        "resource": "docs/specs/old-spec.md",
    }


def test_parse_invoke_action(parser: MarkdownPlanParser):
    """
    Given a valid Markdown plan with an INVOKE action,
    When the plan is parsed,
    Then a valid Plan domain object is returned with correct action data.
    """
    # Arrange
    plan_content = r"""
# Invoke another agent
- **Goal:** Handoff to the Architect.

## Action Plan

### `INVOKE`
- **Agent:** Architect

Handoff to the Architect.

The brief is complete and located at `docs/briefs/01-brief.md`.
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    assert isinstance(result_plan, Plan)
    assert len(result_plan.actions) == 1
    action = result_plan.actions[0]

    expected_message = (
        "Handoff to the Architect.\n\n"
        "The brief is complete and located at `docs/briefs/01-brief.md`."
    )

    assert action.type == "INVOKE"
    assert action.description is None
    assert action.params["agent"] == "Architect"
    assert action.params["message"] == expected_message
