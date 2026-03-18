import pytest

from teddy_executor.core.domain.models import Plan
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser


@pytest.fixture
def parser(container) -> IPlanParser:
    """Resolves the MarkdownPlanParser from the container."""
    return container.resolve(IPlanParser)


def test_parse_create_action(parser: IPlanParser):
    """
    Given a valid Markdown plan with a CREATE action,
    When the plan is parsed,
    Then a valid Plan domain object is returned with correct action data.
    """
    # Arrange
    plan_content = """
# Create a test file
- **Goal:** Create a simple file.

## Rationale
````text
Rationale.
````

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


def test_parse_read_action(parser: IPlanParser):
    """
    Given a valid Markdown plan with a READ action,
    When the plan is parsed,
    Then a valid Plan domain object is returned with correct action data.
    """
    # Arrange
    plan_content = """
# Read a file
- **Goal:** Read the architecture document.

## Rationale
````text
Rationale.
````

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
    assert action.params.get("Description") is None
    assert action.params["resource"] == "docs/ARCHITECTURE.md"


def test_parse_edit_action(parser: IPlanParser):
    """
    Given a valid Markdown plan with a multi-block EDIT action,
    When the plan is parsed,
    Then a valid Plan domain object is returned with correct action data.
    """
    # Arrange
    plan_content = """
# Edit a file
- **Goal:** Update a class.

## Rationale
````text
Rationale.
````

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


def test_parse_edit_action_preserves_indentation_in_find_and_replace(
    parser: IPlanParser,
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

## Rationale
````text
Rationale.
````

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


def test_parse_edit_action_ignores_find_in_codeblock(parser: IPlanParser):
    """
    Given a valid Markdown plan with an EDIT action,
    When the FIND block contains text that looks like another FIND/REPLACE block,
    Then the parser should not be confused and should parse the action correctly.
    """
    # Arrange
    plan_content = r"""
# Edit a file
- **Goal:** Update a class.

## Rationale
````text
Rationale.
````

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


def test_parser_succeeds_on_builder_generated_create_action(parser: IPlanParser):
    """
    This test verifies that the MarkdownPlanBuilder generates a valid CREATE
    action that the refactored stream-based parser can successfully parse.
    """
    from tests.suites.acceptance.plan_builder import MarkdownPlanBuilder

    # Arrange
    builder = MarkdownPlanBuilder("Test Plan")
    builder.add_action(
        "CREATE",
        params={
            "File Path": "new_file.txt",
            "Description": "Create a new file.",
        },
        # Note: The key here is for the builder, but should not be rendered
        # for a CREATE action.
        content_blocks={"Content:": ("text", "Hello, TeDDy!")},
    )
    plan_content = builder.build()

    # Act
    plan = parser.parse(plan_content)

    # Assert
    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.type == "CREATE"
    assert action.params["path"] == "new_file.txt"
    assert action.params["content"] == "Hello, TeDDy!"
    assert action.description == "Create a new file."
