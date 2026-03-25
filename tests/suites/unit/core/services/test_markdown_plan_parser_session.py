import pytest
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser

def test_parser_sets_is_session_true_for_session_paths():
    parser = MarkdownPlanParser()
    content = """# Session Plan
- **Status:** Green 🟢
- **Plan Type:** Implementation
- **Agent:** Pathfinder

## Rationale
```text
Synthesis
```

## Action Plan
### `READ`
- **Resource:** file.txt
"""
    # Test path inside .teddy/sessions/
    plan = parser.parse(content, plan_path=".teddy/sessions/my-session/01/plan.md")
    assert plan.is_session is True

def test_parser_sets_is_session_false_for_non_session_paths():
    parser = MarkdownPlanParser()
    content = """# Manual Plan
- **Status:** Green 🟢
- **Plan Type:** Implementation
- **Agent:** Pathfinder

## Rationale
```text
Synthesis
```

## Action Plan
### `READ`
- **Resource:** file.txt
"""
    # Test path outside .teddy/sessions/
    plan = parser.parse(content, plan_path="some/other/path/plan.md")
    assert plan.is_session is False

def test_parser_defaults_to_not_session_when_path_missing():
    parser = MarkdownPlanParser()
    content = """# No Path Plan
- **Status:** Green 🟢
- **Plan Type:** Implementation
- **Agent:** Pathfinder

## Rationale
```text
Synthesis
```

## Action Plan
### `READ`
- **Resource:** file.txt
"""
    # Test with no path provided
    plan = parser.parse(content)
    assert plan.is_session is False