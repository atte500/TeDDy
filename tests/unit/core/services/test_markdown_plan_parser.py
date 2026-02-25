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

## Rationale
````text
Rationale.
````

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
    assert action.params.get("Description") is None
    assert action.params["command"] == "poetry run pytest"
    assert action.params["expected_outcome"] == "All tests will pass."
    assert action.params["cwd"] == "/tmp/tests"
    assert action.params["env"] == {"API_KEY": "secret", "DEBUG": "1"}


def test_parse_execute_action_with_cd_directive(parser: MarkdownPlanParser):
    """
    Given an EXECUTE action with a `cd` directive in the shell block,
    When the plan is parsed,
    Then the `cwd` is extracted and the `cd` line is stripped from the command.
    """
    # Arrange
    plan_content = """
# Execute a command in a specific directory
- **Goal:** Run a test in a subdirectory.

## Rationale
````text
Rationale.
````

## Action Plan

### `EXECUTE`
- **Description:** Run the test suite in `src/`.
- **Expected Outcome:** All tests will pass.
````shell
cd src/my_dir
poetry run pytest
````
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    assert len(result_plan.actions) == 1
    action = result_plan.actions[0]

    assert action.type == "EXECUTE"
    assert action.params["cwd"] == "src/my_dir"
    assert action.params["command"] == "poetry run pytest"
    assert action.params.get("env") is None


def test_parse_execute_action_with_export_directive(parser: MarkdownPlanParser):
    """
    Given an EXECUTE action with `export` directives in the shell block,
    When the plan is parsed,
    Then the `env` dict is populated and the `export` lines are stripped.
    """
    # Arrange
    plan_content = r"""
# Execute a command with environment variables
- **Goal:** Run a command with custom env vars.

## Rationale
````text
Rationale.
````

## Action Plan

### `EXECUTE`
- **Description:** Run a command with env vars.
- **Expected Outcome:** Success.
````shell
export FOO=bar
export BAZ="qux"
export OTHER='single_quotes'
my_command --do-something
````
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    assert len(result_plan.actions) == 1
    action = result_plan.actions[0]

    assert action.type == "EXECUTE"
    expected_env = {"FOO": "bar", "BAZ": "qux", "OTHER": "single_quotes"}
    assert action.params["env"] == expected_env
    assert action.params["command"] == "my_command --do-something"
    assert action.params.get("cwd") is None


def test_parse_execute_action_with_mixed_directives(parser: MarkdownPlanParser):
    """
    Given an EXECUTE action with both `cd` and `export` directives,
    When the plan is parsed,
    Then both are extracted correctly and stripped from the command.
    """
    # Arrange
    plan_content = r"""
# Execute a command with mixed directives
- **Goal:** Run a test with context.

## Rationale
````text
Rationale.
````

## Action Plan

### `EXECUTE`
- **Description:** Run pytest in tests dir with CI flag.
- **Expected Outcome:** Success.
````shell
cd tests
export CI=true

pytest -k "my_test"
````
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    assert len(result_plan.actions) == 1
    action = result_plan.actions[0]

    assert action.type == "EXECUTE"
    assert action.params["cwd"] == "tests"
    assert action.params["env"] == {"CI": "true"}
    assert action.params["command"] == 'pytest -k "my_test"'


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

## Rationale
````text
Rationale.
````

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

## Rationale
````text
Rationale.
````

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

## Rationale
````text
Rationale.
````

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
    assert action.params.get("Description") is None
    assert action.params["resource"] == "docs/project/specs/old-spec.md"


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

## Rationale
````text
Rationale.
````

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

## Rationale
````text
Rationale.
````

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


def test_parser_normalizes_windows_style_paths(parser: MarkdownPlanParser):
    """
    Given a Markdown plan with Windows-style paths (backslashes) in action metadata,
    When the plan is parsed,
    Then the resulting ActionData parameters should have normalized POSIX-style paths (forward slashes).
    """
    plan_content = """
# Test Windows Paths
- **Status:** Green 🟢
- **Agent:** Developer

## Rationale
````text
Rationale.
````

## Action Plan
### `EDIT`
- **File Path:** [target_dir\\pyproject.toml](/target_dir\\pyproject.toml)
- **Description:** Edit a file.
#### `FIND:`
````text
Hello
````
#### `REPLACE:`
````text
World
````
### `INVOKE`
- **Agent:** Architect
- **Handoff Resources:**
  - [mixed\\path/file.md](/mixed\\path/file.md)

Handoff message.
"""
    # Act
    plan = parser.parse(plan_content)

    # Assert
    assert len(plan.actions) == 2

    edit_action = plan.actions[0]
    assert edit_action.type == "EDIT"
    assert edit_action.params["path"] == "target_dir/pyproject.toml"

    invoke_action = plan.actions[1]
    assert invoke_action.type == "INVOKE"
    assert invoke_action.params["handoff_resources"] == ["mixed/path/file.md"]


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
- **Status:** Green 🟢
- **Agent:** Developer

## Rationale
````text
Rationale.
````

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

    # The parser normalizes all paths to POSIX style (/) at the boundary.
    expected_path = absolute_path.replace("\\", "/")
    assert action.params["resource"] == expected_path


def test_parser_rejects_plan_with_preamble_and_shows_ast_diff(
    parser: MarkdownPlanParser,
):
    """
    Given a Markdown plan with conversational text (a preamble) before the H1,
    When the parser parses it,
    Then it should raise an InvalidPlanError detailing the structural mismatch
    with a Desired vs Actual AST diff.
    """
    from teddy_executor.core.ports.inbound.plan_parser import InvalidPlanError

    plan_content = """
Here is the plan you asked for.

# My Plan
- **Status:** Green 🟢
- **Plan Type:** Test
- **Agent:** Dev

## Rationale
```text
Synthesis, etc.
```

## Action Plan
### `EXECUTE`
- **Description:** test
```shell
echo 1
```
"""

    with pytest.raises(InvalidPlanError) as excinfo:
        parser.parse(plan_content)

    error_msg = str(excinfo.value)
    assert "Plan structure is invalid." in error_msg
    assert "--- Expected Document Structure ---" in error_msg
    assert "--- Actual Document Structure ---" in error_msg
    assert "[000] Paragraph" in error_msg
    assert "<-- MISMATCH" in error_msg


def test_parser_raises_error_on_unknown_action(parser: MarkdownPlanParser):
    """
    Given a Markdown plan with an unknown action header,
    When the parser parses it,
    Then it should raise an InvalidPlanError.
    """
    from teddy_executor.core.ports.inbound.plan_parser import InvalidPlanError

    plan_content = """
# Test Plan
- **Status:** Green 🟢
- **Plan Type:** Test
- **Agent:** Dev

## Rationale
````text
Rationale.
````

## Action Plan

### `UNKNOWN_ACTION`
- **Description:** This should fail.
    """

    with pytest.raises(InvalidPlanError) as excinfo:
        parser.parse(plan_content)

    assert "Unknown action type: UNKNOWN_ACTION" in str(excinfo.value)


def test_parser_raises_error_on_thematic_break_between_actions(
    parser: MarkdownPlanParser,
):
    """
    Given a Markdown plan with a thematic break (---) between two actions,
    When the parser parses it,
    Then it should raise an InvalidPlanError.
    """
    from teddy_executor.core.ports.inbound.plan_parser import InvalidPlanError

    plan_content = """
# Test Plan with Thematic Break Separator
- **Status:** Green 🟢
- **Agent:** Developer

## Rationale
````text
Rationale.
````

## Action Plan
### `CREATE`
- **File Path:** [file1.txt](/file1.txt)
- **Description:** First file.
````text
content1
````
---
### `CREATE`
- **File Path:** [file2.txt](/file2.txt)
- **Description:** Second file.
````text
content2
````
"""
    # Act & Assert
    with pytest.raises(InvalidPlanError) as excinfo:
        parser.parse(plan_content)

    error_msg = str(excinfo.value)
    assert "Plan structure is invalid. Expected a Level 3 Action Heading" in error_msg
    assert "--- Actual Document Structure ---" in error_msg
    assert "ThematicBreak  <-- MISMATCH" in error_msg


def test_parser_raises_error_on_malformed_structure_between_actions(
    parser: MarkdownPlanParser,
):
    """
    Given a Markdown plan with free text between action blocks,
    When the parser parses it,
    Then it should raise an InvalidPlanError with a clear AST diff.
    """
    from teddy_executor.core.ports.inbound.plan_parser import InvalidPlanError

    plan_content = """
# Test Plan
- **Status:** Green 🟢
- **Plan Type:** Test
- **Agent:** Dev

## Rationale
````text
Rationale.
````

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

    error_msg = str(excinfo.value)
    assert "Plan structure is invalid. Expected a Level 3 Action Heading" in error_msg
    assert "Unexpected content found" not in error_msg  # Redundant phrasing removed
    assert "--- Actual Document Structure ---" in error_msg
    assert 'Paragraph: "This is some free text that sh..."  <-- MISMATCH' in error_msg


def test_parser_succeeds_on_builder_generated_create_action(parser: MarkdownPlanParser):
    """
    This test verifies that the MarkdownPlanBuilder generates a valid CREATE
    action that the refactored stream-based parser can successfully parse.
    """
    from tests.acceptance.plan_builder import MarkdownPlanBuilder

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


def test_parser_rejects_improperly_nested_code_fences(parser: MarkdownPlanParser):
    """
    Given a markdown plan with an improperly nested code block,
    When the plan is parsed,
    Then the parser must reject it with an InvalidPlanError.
    """
    from teddy_executor.core.ports.inbound.plan_parser import InvalidPlanError

    # This plan is invalid because the inner markdown block uses ```
    # which is the same as the outer fence for the CREATE action's content.
    plan_content = """
# Plan to Create a Failing Plan
- **Status:** Green 🟢
- **Agent:** Developer

## Rationale
````text
Rationale.
````

## Action Plan

### `CREATE`
- **File Path:** failing_plan.md
- **Description:** Create a plan that has invalid nesting.
```markdown
# This is the inner plan that will be created

## Action Plan
### `EXECUTE`
- **Description:** A command.
```shell
echo "hello"
```
```
"""
    with pytest.raises(InvalidPlanError) as excinfo:
        parser.parse(plan_content)

    error_msg = str(excinfo.value)
    assert "Plan structure is invalid. Expected a Level 3 Action Heading" in error_msg
    assert "--- Actual Document Structure ---" in error_msg


def test_parser_rejects_user_provided_invalidly_nested_edit_plan(
    parser: MarkdownPlanParser,
):
    """
    This test uses a real-world example provided by the user that should fail
    due to an improperly nested code block within an EDIT action's REPLACE block.
    The inner fence (````shell) has the same length as the outer fence (````python).
    """
    from teddy_executor.core.ports.inbound.plan_parser import InvalidPlanError

    plan_content = r'''
# Write Failing Unit Test for `cd` Directive
- **Status:** Green 🟢
- **Plan Type:** RED Phase
- **Agent:** Developer

## Rationale
````text
Rationale.
````

## Action Plan

### `EDIT`
- **File Path:** [tests/unit/core/services/test_markdown_plan_parser.py](/tests/unit/core/services/test_markdown_plan_parser.py)
- **Description:** Add a new failing unit test.

#### `FIND:`
````python
def test_parse_execute_action(parser: MarkdownPlanParser):
    """
    Given a valid Markdown plan with an EXECUTE action,
    When the plan is parsed,
    Then a valid Plan domain object is returned with correct action data.
    """
````
#### `REPLACE:`
````python
def test_parse_execute_action_with_cd_directive(parser: MarkdownPlanParser):
    """
    Given an EXECUTE action with a `cd` directive in the shell block,
    When the plan is parsed,
    Then the `cwd` is extracted and the `cd` line is stripped from the command.
    """
    # Arrange
    plan_content = """
# Execute a command in a specific directory
- **Goal:** Run a test in a subdirectory.

## Rationale
````text
Rationale.
````

## Action Plan

### `EXECUTE`
- **Description:** Run the test suite in `src/`.
- **Expected Outcome:** All tests will pass.
````shell
cd src/my_dir
poetry run pytest
````
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    assert len(result_plan.actions) == 1
    action = result_plan.actions[0]

    assert action.type == "EXECUTE"
    assert action.params["cwd"] == "src/my_dir"
    assert action.params["command"] == "poetry run pytest"
    assert action.params.get("env") is None


def test_parse_execute_action(parser: MarkdownPlanParser):
    """
    Given a valid Markdown plan with an EXECUTE action,
    When the plan is parsed,
    Then a valid Plan domain object is returned with correct action data.
    """
````
'''
    with pytest.raises(InvalidPlanError) as excinfo:
        parser.parse(plan_content)

    # The corrected _parse_edit_action leaves the malformed content (a Paragraph)
    # in the stream, which is then caught by the main _parse_actions loop.
    error_msg = str(excinfo.value)
    assert "Plan structure is invalid. Expected a Level 3 Action Heading" in error_msg
    assert "--- Actual Document Structure ---" in error_msg
    assert "<-- MISMATCH" in error_msg


def test_parser_accepts_properly_nested_code_fences(parser: MarkdownPlanParser):
    """
    Given a markdown plan with a properly nested code block,
    When the plan is parsed,
    Then the parser must accept it and parse correctly.
    """
    # This plan is valid because the outer fence (````) is longer
    # than the inner fence (```).
    plan_content = r"""
# Plan to Create a Valid Plan
- **Status:** Green 🟢
- **Agent:** Developer

## Rationale
````text
Rationale.
````

## Action Plan

### `CREATE`
- **File Path:** [valid_plan.md](/valid_plan.md)
- **Description:** Create a plan with valid nesting.
````markdown
# This is the inner plan that will be created

## Action Plan
### `EXECUTE`
- **Description:** A command.
```shell
echo "hello"
```
````
"""
    plan = parser.parse(plan_content)
    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.type == "CREATE"
    assert action.params["path"] == "valid_plan.md"
    expected_content = r"""# This is the inner plan that will be created

## Action Plan
### `EXECUTE`
- **Description:** A command.
```shell
echo "hello"
```"""
    assert action.params["content"] == expected_content
    from tests.acceptance.plan_builder import MarkdownPlanBuilder

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
