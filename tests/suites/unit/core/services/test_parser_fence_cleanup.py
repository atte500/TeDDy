"""
Unit tests for parser resilience: trailing text cleanup within code fences.
"""

from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser


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
~~~~~~
test rationale
~~~~~~

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
