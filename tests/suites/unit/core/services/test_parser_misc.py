import pytest

from teddy_executor.core.ports.inbound.plan_parser import IPlanParser


@pytest.fixture
def parser(container) -> IPlanParser:
    """Resolves the MarkdownPlanParser from the container."""
    return container.resolve(IPlanParser)


def test_parser_normalizes_windows_style_paths(parser: IPlanParser):
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
- **Description:** Handoff message.
- **Handoff Resources:**
  - [mixed\\path/file.md](/mixed\\path/file.md)
"""
    # Act
    plan = parser.parse(plan_content)

    # Assert
    expected_action_count = 2
    assert len(plan.actions) == expected_action_count

    edit_action = plan.actions[0]
    assert edit_action.type == "EDIT"
    assert edit_action.params["path"] == "target_dir/pyproject.toml"

    invoke_action = plan.actions[1]
    assert invoke_action.type == "INVOKE"
    assert invoke_action.params["message"] == "Handoff message."
    assert invoke_action.params["handoff_resources"] == ["mixed/path/file.md"]


def test_parser_accepts_properly_nested_code_fences(parser: IPlanParser):
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
