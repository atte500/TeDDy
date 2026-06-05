"""
Unit tests for parser resilience: trailing text cleanup within code fences.
"""

from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser


def test_backtick_closing_fence_trailing_text_stripped():
    """
    Given a plan whose CREATE action has a 6-backtick closing fence with trailing text,
    When the plan is parsed,
    Then the trailing text should be stripped so the code block content is clean.
    """
    parser = MarkdownPlanParser()
    # The CREATE action uses a 6-backtick fence with trailing text.
    # Without preprocessing, "~~~~~~ trailing extra text" is NOT a valid closing
    # fence (CommonMark disallows trailing non-space content on closing fences).
    # After _FencePreProcessor strips it, "~~~~~~" becomes a valid closing fence.
    plan = """# Test Plan
- **Agent:** Dev
- **Plan Type:** Test
- **Status:** Pending

## Rationale
~~~~~~~~~
test rationale
~~~~~~~~~

## Action Plan

### `CREATE`
- **File Path:** [/test.txt](/test.txt)
- **Description:** Create a test file.
~~~~~~
Hello, World!
~~~~~~ trailing extra text
"""
    result = parser.parse(plan)
    assert len(result.actions) == 1
    assert result.actions[0].type == "CREATE"
    assert result.actions[0].params["content"] == "Hello, World!"


def test_parser_ignores_trailing_text_on_fence_opener():
    """
    Trailing text after the fence language identifier (e.g. ~~~~~~text extra)
    should be ignored and not cause a parse error.
    """
    parser = MarkdownPlanParser()
    plan = """# Test Plan
- **Agent:** Dev
- **Plan Type:** Implementation
- **Status:** Pending

## Rationale
~~~~~~~~~
test rationale
~~~~~~~~~

## Action Plan

### READ
- **Resource:** file.md
~~~~~~text trailing extra
content
~~~~~~
"""
    result = parser.parse(plan)
    assert len(result.actions) == 1
    assert result.actions[0].type == "READ"
    assert result.actions[0].params.get("resource") == "file.md"
