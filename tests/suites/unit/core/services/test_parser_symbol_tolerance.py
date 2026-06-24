"""Regression test: action names with trailing symbols are accepted."""

from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser


def test_read_action_with_trailing_symbols():
    """Verifies that ### READ** is parsed as a READ action."""
    plan_content = """# Title
- **Agent:** Test
- **Plan Type:** Exploration

## Rationale
~~~~~~
Test rationale
~~~~~~

## Action Plan

### `READ**
- **Resource:** [test.txt](/test.txt)
"""
    parser = MarkdownPlanParser()
    plan = parser.parse(plan_content)
    assert len(plan.actions) == 1
    assert plan.actions[0].type == "READ"
    assert plan.actions[0].params.get("resource") == "test.txt"


def test_edit_action_with_trailing_symbols():
    """Verifies that ### EDIT** is parsed as an EDIT action."""
    plan_content = """# Title
- **Agent:** Test
- **Plan Type:** Exploration

## Rationale
~~~~~~
Test rationale
~~~~~~

## Action Plan

### `EDIT**
- **File Path:** [test.txt](/test.txt)

#### `FIND:`
~~~~~~
old content
~~~~~~
#### `REPLACE:`
~~~~~~
new content
~~~~~~
"""
    parser = MarkdownPlanParser()
    plan = parser.parse(plan_content)
    assert len(plan.actions) == 1
    assert plan.actions[0].type == "EDIT"


def test_execute_action_with_trailing_symbols():
    """Verifies that ### EXECUTE** is parsed as an EXECUTE action."""
    plan_content = """# Title
- **Agent:** Test
- **Plan Type:** Exploration

## Rationale
~~~~~~
Test rationale
~~~~~~

## Action Plan

### `EXECUTE**
- **Description:** Run a command
~~~~~~
echo hello
~~~~~~
"""
    parser = MarkdownPlanParser()
    plan = parser.parse(plan_content)
    assert len(plan.actions) == 1
    assert plan.actions[0].type == "EXECUTE"


def test_create_action_with_trailing_symbols():
    """Verifies that ### CREATE** is parsed as a CREATE action."""
    plan_content = """# Title
- **Agent:** Test
- **Plan Type:** Exploration

## Rationale
~~~~~~
Test rationale
~~~~~~

## Action Plan

### `CREATE**
- **File Path:** [test.txt](/test.txt)
~~~~~~
content
~~~~~~
"""
    parser = MarkdownPlanParser()
    plan = parser.parse(plan_content)
    assert len(plan.actions) == 1
    assert plan.actions[0].type == "CREATE"


def test_research_action_with_trailing_symbols():
    """Verifies that ### RESEARCH** is parsed as a RESEARCH action."""
    plan_content = """# Title
- **Agent:** Test
- **Plan Type:** Exploration

## Rationale
~~~~~~
Test rationale
~~~~~~

## Action Plan

### `RESEARCH**
- **Description:** Search something
~~~~~~
query
~~~~~~
"""
    parser = MarkdownPlanParser()
    plan = parser.parse(plan_content)
    assert len(plan.actions) == 1
    assert plan.actions[0].type == "RESEARCH"


def test_line_continuation_symbols_are_stripped():
    """Verifies that normal actions without symbols still work."""
    plan_content = """# Title
- **Agent:** Test
- **Plan Type:** Exploration

## Rationale
~~~~~~
Test rationale
~~~~~~

## Action Plan

### `READ`
- **Resource:** [test.txt](/test.txt)
"""
    parser = MarkdownPlanParser()
    plan = parser.parse(plan_content)
    assert len(plan.actions) == 1
    assert plan.actions[0].type == "READ"
