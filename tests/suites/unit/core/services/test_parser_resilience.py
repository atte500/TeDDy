from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser


def test_parser_skips_inter_action_whitespace_blocks():
    """
    R-10-12: The parser should be resilient to whitespace-only code blocks
    (indented spaces) between action blocks, as these are often artifacts
    of AI or user formatting.
    """
    parser = MarkdownPlanParser()
    # 10 spaces between actions
    indent = " " * 10
    plan = f"""# Resilience Test
- **Agent:** Debugger
- **Plan Type:** Probing
- **Status:** SUCCESS

## Rationale
~~~~~~
Rationale content...
~~~~~~

## Action Plan

### READ
- **Resource:** file1.py
{indent}
### READ
- **Resource:** file2.py
"""
    parsed_plan = parser.parse(plan)

    assert len(parsed_plan.actions) == 2
    assert parsed_plan.actions[0].params["resource"] == "file1.py"
    assert parsed_plan.actions[1].params["resource"] == "file2.py"
