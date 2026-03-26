import pytest
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser


@pytest.fixture
def parser(container) -> IPlanParser:
    """Resolves the MarkdownPlanParser from the container."""
    return container.resolve(IPlanParser)


def test_parser_sets_selected_true_for_isolated_terminal_action(parser: IPlanParser):
    plan_content = """
# Isolated Prompt
- **Status:** Green 🟢
- **Plan Type:** Test
- **Agent:** Pathfinder

## Rationale
````text
Test
````

## Action Plan

### `PROMPT`
This is a test prompt.
"""
    plan = parser.parse(plan_content)
    assert len(plan.actions) == 1
    assert plan.actions[0].selected is True


def test_parser_sets_selected_false_for_mixed_terminal_action(parser: IPlanParser):
    plan_content = """
# Mixed Plan
- **Status:** Green 🟢
- **Plan Type:** Test
- **Agent:** Pathfinder

## Rationale
````text
Test
````

## Action Plan

### `EXECUTE`
- **Description:** ls
````shell
ls
````

### `PROMPT`
This is a test prompt.

### `INVOKE`
- **Agent:** Architect
- **Description:** handoff
"""
    plan = parser.parse(plan_content)
    expected_actions = 3
    assert len(plan.actions) == expected_actions
    assert plan.actions[0].selected is True  # EXECUTE
    assert plan.actions[1].selected is False  # PROMPT
    assert plan.actions[2].selected is False  # INVOKE
