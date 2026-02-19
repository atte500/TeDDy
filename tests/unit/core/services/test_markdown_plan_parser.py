import os

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
        "Description": "Read the current architectural conventions.",
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

#### `FIND:`
````python
class MyClass:
    pass
````
#### `REPLACE:`
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
- **Resource:** [docs/project/specs/old-spec.md](/docs/project/specs/old-spec.md)
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
        "Description": "Remove the old specification.",
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
- **Handoff Resources:**
  - [docs/briefs/new-feature.md](/docs/briefs/new-feature.md)

Handoff to the Architect.

The brief is complete.
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    assert isinstance(result_plan, Plan)
    assert len(result_plan.actions) == 1
    action = result_plan.actions[0]

    expected_message = "Handoff to the Architect.\n\nThe brief is complete."

    assert action.type == "INVOKE"
    assert action.description is None
    assert action.params["agent"] == "Architect"
    assert action.params["message"] == expected_message
    assert "handoff_resources" in action.params
    assert action.params["handoff_resources"] == ["docs/briefs/new-feature.md"]


def test_parse_edit_action_preserves_indentation_in_find_and_replace(
    parser: MarkdownPlanParser,
):
    """
    Given a Markdown plan with an EDIT action,
    When the find and replace blocks contain critical indentation,
    Then the parser should preserve this indentation exactly, except for the
    single trailing newline, which is consistently stripped by the AST parser.
    """
    from textwrap import dedent

    # Arrange
    indented_find_block = dedent(
        """\
        def hello():
            print("Hello")
    """
    )
    indented_replace_block = dedent(
        """\
        def world():
            print("World")
    """
    )

    plan_content = f"""
# Edit a file with indentation
- **Goal:** Update a class.

## Action Plan

### `EDIT`
- **File Path:** [/path/to/file.py](/path/to/file.py)
- **Description:** A test edit with indentation.

#### `FIND:`
````python
{indented_find_block}
````
#### `REPLACE:`
````python
{indented_replace_block}
````
"""
    # Act
    plan = parser.parse(plan_content)

    # Assert
    assert len(plan.actions) == 1
    edit_action = plan.actions[0]
    assert edit_action.type == "EDIT"

    assert len(edit_action.params["edits"]) == 1
    edit_block = edit_action.params["edits"][0]

    # The mistletoe parser strips the single trailing newline from a code block.
    # We must rstrip the expected value to match this valid behavior.
    assert edit_block["find"] == indented_find_block.rstrip("\n")
    assert edit_block["replace"] == indented_replace_block.rstrip("\n")


def test_parse_edit_action_ignores_find_in_codeblock(parser: MarkdownPlanParser):
    """
    Given a valid Markdown plan with an EDIT action,
    When the FIND block contains text that looks like another FIND/REPLACE block,
    Then the parser should not be confused and should parse the action correctly.
    """
    # Arrange
    plan_content = r"""
# Edit a file
- **Goal:** Update a class.

## Action Plan

### `EDIT`
- **File Path:** [src/my_class.py](/src/my_class.py)
- **Description:** Add a new method.

#### `FIND:`
````markdown
Some documentation about `FIND:` blocks.
#### `FIND:`
This should be ignored.
#### `REPLACE:`
This too.
````
#### `REPLACE:`
````markdown
New documentation.
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

    expected_find = """Some documentation about `FIND:` blocks.
#### `FIND:`
This should be ignored.
#### `REPLACE:`
This too."""

    assert action.params["edits"][0]["find"] == expected_find
    assert action.params["edits"][0]["replace"] == "New documentation."


def test_parse_return_action(parser: MarkdownPlanParser):
    """
    Given a valid Markdown plan with a RETURN action,
    When the plan is parsed,
    Then a valid Plan domain object is returned with correct action data.
    """
    # Arrange
    plan_content = r"""
# Conclude a sub-task
- **Goal:** Handoff to the calling agent.

## Action Plan

### `RETURN`
- **Handoff Resources:**
  - [docs/rca/the-bug.md](/docs/rca/the-bug.md)
  - [spikes/fix-script.sh](/spikes/fix-script.sh)

My analysis is complete. The root cause and a verified fix are attached.
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    assert isinstance(result_plan, Plan)
    assert len(result_plan.actions) == 1
    action = result_plan.actions[0]

    expected_message = (
        "My analysis is complete. The root cause and a verified fix are attached."
    )

    assert action.type == "RETURN"
    assert action.description is None
    assert action.params["message"] == expected_message
    assert "handoff_resources" in action.params
    assert action.params["handoff_resources"] == [
        "docs/rca/the-bug.md",
        "spikes/fix-script.sh",
    ]


def test_parse_read_action_with_absolute_path(parser):
    """
    Verify that the parser preserves a true absolute path on the current OS,
    and does not mistakenly treat it as project-root-relative.
    """
    # Arrange: Use an appropriate absolute path for the current OS
    if os.name == "nt":
        absolute_path = "C:\\Users\\test.txt"
    else:
        absolute_path = "/tmp/test.txt"

    plan_content = f"""
# Test Plan
## Action Plan
### `READ`
- **Resource:** [{absolute_path}]({absolute_path})
- **Description:** Read a file with an absolute path.
"""
    # Act
    plan = parser.parse(plan_content)

    # Assert
    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.type == "READ"
    assert action.params["resource"] == absolute_path


def test_parser_raises_error_on_unknown_action(parser: MarkdownPlanParser):
    """
    Given a Markdown plan with an unknown action header,
    When the parser parses it,
    Then it should raise an InvalidPlanError.
    """
    from teddy_executor.core.ports.inbound.plan_parser import InvalidPlanError

    plan_content = """
# Test Plan
- Status: Green 🟢
- Plan Type: Test
- Agent: Dev

## Rationale
Rationale.

## Action Plan

### `UNKNOWN_ACTION`
- **Description:** This should fail.
    """

    with pytest.raises(InvalidPlanError) as excinfo:
        parser.parse(plan_content)

    assert "Unknown action type: UNKNOWN_ACTION" in str(excinfo.value)


def test_parser_raises_error_on_malformed_structure_between_actions(
    parser: MarkdownPlanParser,
):
    """
    Given a Markdown plan with free text between action blocks,
    When the parser parses it,
    Then it should raise an InvalidPlanError.
    """
    from teddy_executor.core.ports.inbound.plan_parser import InvalidPlanError

    plan_content = """
# Test Plan
- Status: Green 🟢
- Plan Type: Test
- Agent: Dev

## Rationale
Rationale.

## Action Plan

### `EXECUTE`
- **Description:** First action.
- **Expected Outcome:** Success.
- **cwd:** /tmp
````shell
echo 1
````

This is some free text that shouldn't be here.

### `EXECUTE`
- **Description:** Second action.
- **Expected Outcome:** Success.
- **cwd:** /tmp
````shell
echo 2
````
    """

    with pytest.raises(InvalidPlanError) as excinfo:
        parser.parse(plan_content)

    assert "Unexpected content found between actions" in str(excinfo.value)
