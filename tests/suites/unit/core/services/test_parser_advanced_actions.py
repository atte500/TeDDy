import pytest

from teddy_executor.core.domain.models import Plan
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser


@pytest.fixture
def parser(container) -> IPlanParser:
    """Resolves the MarkdownPlanParser from the container."""
    return container.resolve(IPlanParser)


def test_parse_execute_action(parser: IPlanParser):
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


def test_parse_execute_action_with_colon(parser: IPlanParser):
    """
    Verify that a command with a colon is parsed correctly.
    (Migrated from acceptance tests)
    """
    # Arrange
    plan_content = """
# Test Execute Action
- **Goal:** Test colon.

## Rationale
````text
Rationale.
````

## Action Plan

### `EXECUTE`
- **Description:** Run a command with a colon.
````shell
echo hello:world
````
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    assert result_plan.actions[0].params["command"] == "echo hello:world"


def test_parse_research_action(parser: IPlanParser):
    """
    Given a valid Markdown plan with a RESEARCH action with multiple queries,
    When the plan is parsed,
    Then a valid Plan domain object is returned with correct action data.
    """
    # Arrange
    plan_content = """
# Research a topic
- Status: Green 🟢
- Agent: Pathfinder

## Rationale
````text
Rationale.
````

## Action Plan

### `RESEARCH`
- **Description:** Find libraries for parsing Markdown.
````text
python markdown ast library
  multi-line within block
````
````text
another block query
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
        "multi-line within block",
        "another block query",
    ]


def test_parse_prompt_action(parser: IPlanParser):
    """
    Given a valid Markdown plan with a PROMPT action,
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

### `PROMPT`
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

    assert action.type == "PROMPT"
    assert action.description is None  # No description metadata for this action
    assert action.params["prompt"] == expected_prompt


def test_parse_prompt_action_with_reference_files(parser: IPlanParser):
    """
    Given a PROMPT action with a "Reference Files" metadata list,
    When the plan is parsed,
    Then the resources should be extracted and the remaining message preserved.
    """
    # Arrange
    plan_content = r"""
# Chat with the user
- Status: Green 🟢
- Agent: Pathfinder

## Rationale
````text
Rationale.
````

## Action Plan

### `PROMPT`
- **Reference Files:**
  - [important.txt](/important.txt)

Please look at this file.
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    action = result_plan.actions[0]
    assert "handoff_resources" in action.params
    assert action.params["handoff_resources"] == ["important.txt"]
    assert action.params["prompt"] == "Please look at this file."


def test_parse_prune_action(parser: IPlanParser):
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


def test_parse_invoke_action_without_blank_line_before_message(parser: IPlanParser):
    """
    Given an INVOKE action where the message immediately follows the metadata list,
    When the plan is parsed,
    Then it should correctly identify the message.
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
- **Description:** Handoff to the Architect. The brief is complete.
- **Handoff Resources:**
  - [docs/briefs/new-feature.md](/docs/briefs/new-feature.md)
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    assert isinstance(result_plan, Plan)
    assert len(result_plan.actions) == 1
    action = result_plan.actions[0]

    expected_message = "Handoff to the Architect. The brief is complete."

    assert action.type == "INVOKE"
    assert action.params["agent"] == "Architect"
    assert "handoff_resources" in action.params
    assert action.params["handoff_resources"] == ["docs/briefs/new-feature.md"]
    assert action.params["message"] == expected_message


def test_parse_invoke_action(parser: IPlanParser):
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
- **Description:** Handoff to the Architect.
- **Handoff Resources:**
  - [docs/briefs/new-feature.md](/docs/briefs/new-feature.md)
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    assert isinstance(result_plan, Plan)
    assert len(result_plan.actions) == 1
    action = result_plan.actions[0]

    expected_message = "Handoff to the Architect."

    assert action.type == "INVOKE"
    assert action.description == expected_message
    assert action.params["agent"] == "Architect"
    assert action.params["message"] == expected_message
    assert "handoff_resources" in action.params
    assert action.params["handoff_resources"] == ["docs/briefs/new-feature.md"]


def test_parse_invoke_action_with_reference_files(parser: IPlanParser):
    """
    Given a valid Markdown plan with an INVOKE action using "Reference Files",
    When the plan is parsed,
    Then the resources should be correctly extracted.
    """
    # Arrange
    plan_content = r"""
# Invoke another agent
- Status: Green 🟢
- Agent: Pathfinder

## Rationale
````text
Rationale.
````

## Action Plan

### `INVOKE`
- **Agent:** Architect
- **Description:** Handoff message.
- **Reference Files:**
  - [docs/ref.md](/docs/ref.md)
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    action = result_plan.actions[0]
    assert "handoff_resources" in action.params
    assert action.params["handoff_resources"] == ["docs/ref.md"]


def test_parse_return_action(parser: IPlanParser):
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
- **Description:** My analysis is complete.
- **Handoff Resources:**
  - [docs/rca/the-bug.md](/docs/rca/the-bug.md)
  - [spikes/fix-script.sh](/spikes/fix-script.sh)
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    assert isinstance(result_plan, Plan)
    assert len(result_plan.actions) == 1
    action = result_plan.actions[0]

    expected_message = "My analysis is complete."

    assert action.type == "RETURN"
    assert action.description == expected_message
    assert action.params["message"] == expected_message
    assert "handoff_resources" in action.params
    assert action.params["handoff_resources"] == [
        "docs/rca/the-bug.md",
        "spikes/fix-script.sh",
    ]


def test_parser_accepts_multiline_execute_for_later_validation(
    parser: IPlanParser,
):
    """
    Given an EXECUTE action with multiple commands,
    When the plan is parsed,
    Then the command should be passed through unmodified for the validator to handle.
    """
    # Arrange
    plan_content = r"""
# Execute a multiline command
- **Goal:** Test parser leniency.

## Rationale
````text
Rationale.
````

## Action Plan

### `EXECUTE`
- **Description:** Run a multiline command.
````shell
echo "hello"
echo "world"
````
"""
    # Act
    result_plan = parser.parse(plan_content)

    # Assert
    assert len(result_plan.actions) == 1
    action = result_plan.actions[0]

    assert action.type == "EXECUTE"
    assert action.params["command"] == 'echo "hello"\necho "world"'
