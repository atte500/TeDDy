import pytest

from teddy_executor.core.ports.inbound.plan_parser import IPlanParser


@pytest.fixture
def parser(container) -> IPlanParser:
    """Resolves the MarkdownPlanParser from the container."""
    return container.resolve(IPlanParser)


def test_parser_raises_error_on_unknown_action(parser: IPlanParser):
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
    parser: IPlanParser,
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
    assert "ThematicBreak <-- MISMATCH" in error_msg


def test_parser_raises_error_on_malformed_structure_between_actions(
    parser: IPlanParser,
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
    assert 'Paragraph: "This is some free text that sh..." <-- MISMATCH' in error_msg


def test_parser_rejects_improperly_nested_code_fences(parser: IPlanParser):
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
    parser: IPlanParser,
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
def test_parse_execute_action(parser: IPlanParser):
    """
    Given a valid Markdown plan with an EXECUTE action,
    When the plan is parsed,
    Then a valid Plan domain object is returned with correct action data.
    """
````
#### `REPLACE:`
````python
def test_parse_execute_action_with_cd_directive(parser: IPlanParser):
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


def test_parse_execute_action(parser: IPlanParser):
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


def test_parser_raises_error_if_no_title_found(parser: IPlanParser):
    """
    Given a Markdown plan with no H1 heading,
    When the parser parses it,
    Then it should raise an InvalidPlanError.
    """
    from teddy_executor.core.ports.inbound.plan_parser import InvalidPlanError

    plan_content = """
This is a document without a title.
## Just a Sub-heading
- Some item
"""
    with pytest.raises(InvalidPlanError) as excinfo:
        parser.parse(plan_content)

    assert "No Level 1 heading found" in str(excinfo.value)


def test_parser_raises_error_with_indicator_on_missing_replace_block(
    parser: IPlanParser,
):
    """
    Scenario 1: Missing REPLACE block in EDIT action
    Verifies that a plan with an EDIT action missing a REPLACE block
    triggers an InvalidPlanError containing the shared MISMATCH indicator.
    """
    from teddy_executor.core.ports.inbound.plan_parser import InvalidPlanError

    plan_content = """# Malformed Plan
- Status: Green 🟢
- Plan Type: test
- Agent: test

## Rationale
````
Test rationale
````

## Action Plan

### `EDIT`
- **File Path:** dummy.txt
- **Description:** Missing replace block

#### `FIND:`
````text
find me
````

This paragraph is NOT a REPLACE heading.
"""
    with pytest.raises(InvalidPlanError) as excinfo:
        parser.parse(plan_content)

    error_msg = str(excinfo.value)
    assert "Missing REPLACE block after FIND block" in error_msg
    assert (
        "Missing REPLACE block after FIND block <-- MISMATCH"
        not in error_msg.splitlines()[0]
    )
    assert 'Paragraph: "This paragraph is NOT a REPLAC..." <-- MISMATCH' in error_msg


def test_parser_raises_error_with_indicator_on_structural_mismatch(parser: IPlanParser):
    """
    Scenario 2: Consistent Top-Level Structural Errors
    Verifies that a plan with an invalid top-level structure (missing Rationale)
    triggers an error containing the MISMATCH indicator in the AST summary.
    """
    from teddy_executor.core.ports.inbound.plan_parser import InvalidPlanError

    plan_content = """# Missing Rationale Plan
- Status: Green 🟢
- Plan Type: test
- Agent: test

## Action Plan
### `READ`
- Resource: README.md
"""
    with pytest.raises(InvalidPlanError) as excinfo:
        parser.parse(plan_content)

    error_msg = str(excinfo.value)
    assert "Plan structure is invalid" in error_msg
    # Verify the specific mismatch location in the AST summary
    assert '[002] Heading (Level 2): "Action Plan..." <-- MISMATCH' in error_msg
