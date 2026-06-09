# Task: Strip Preamble Before H1 in Plan Parser

## Business Goal
Prevent preamble text (any content before the first `#` heading in a plan payload) from causing structural validation errors and from appearing in the final parsed `plan.md`. Preamble text should be silently stripped during parsing.

## Context
The `MarkdownPlanParser` in `markdown_plan_parser.py` receives a raw `plan_content` string and parses it into a `Plan` domain object. Currently, any text before the first `#` heading (Level 1 Heading / Title) causes a structural validation error because `_parse_strict_top_level()` strictly expects an H1 at index 0 of the AST stream.

The fix is to strip preamble text (any content before the first `# ` heading) during parsing, before the AST is constructed. This ensures:
- No structural validation errors from preamble content
- No preamble text in the final parsed `plan.md`
- Preamble is silently ignored, as if it was never there

## Implementation Steps

### Step 1: Add preamble stripping logic to `MarkdownPlanParser.parse()`
- **File:** [src/teddy_executor/core/services/markdown_plan_parser.py](/src/teddy_executor/core/services/markdown_plan_parser.py)
- **Change:** In the `parse()` method, after `clean_content = plan_content.rstrip()` and before `processed_content = self._preprocessor.process(clean_content)`, add a preamble stripping step.

Logic:
1. Find the first occurrence of `# ` (a level-1 Markdown heading indicator) in `clean_content`.
2. If text exists before the first `# ` (after leading whitespace), strip it, keeping everything from the `#` character onward.
3. If no `# ` is found (e.g., the plan has no title), let the existing empty-content and structural validation handle it.
4. Edge case: If the `# ` is at index 0 (no preamble), do nothing.

Implementation approach:
```python
# Strip preamble (text before the first # heading)
first_h1 = clean_content.find("# ")
if first_h1 > 0:
    clean_content = clean_content[first_h1:]
```

The `> 0` condition ensures we only strip if there's actual preamble text before the `# ` (index 0 means `# ` is at the start, so no preamble). This also naturally handles edge cases like `# ` appearing inside code fences or inline code — since Finder operates on raw text, not parsed AST, the `clean_content` is unprocessed Markdown where `# ` could appear in code blocks. However, this is acceptable because:
- If preamble contains a code block with `# ` inside it, Finder would match the first occurrence inside the code block, and the "preamble" text before that would be stripped (which is correct — it IS preamble before the first real heading).
- The first `# ` that's actually a heading will still be found correctly.
- If preamble contains `# ` as raw text (not inside a code block), that's an edge case where the preamble itself has Markdown-like content — stripping it is correct behavior.

### Step 2: Add test cases for preamble stripping
- **File:** [tests/suites/unit/core/services/test_parser_errors.py](/tests/suites/unit/core/services/test_parser_errors.py)
- **Change:** Add test cases to verify:
  1. Preamble text before H1 is silently stripped (no validation error, plan parses correctly).
  2. Preamble text does NOT appear in the parsed plan's `raw_content`.
  3. Preamble with code fences inside it is handled correctly.
  4. Preamble with only whitespace before H1 is handled correctly (no stripping needed).
  5. Plan with no preamble (current behavior) continues to work correctly.

Tests must build plan strings manually with preamble prepended, since `MarkdownPlanBuilder` always starts with `# Title`.

```python
def test_parser_strips_preamble_text_before_h1(parser: IPlanParser):
    """Preamble text before # heading should be silently stripped."""
    preamble = "Some text before the plan.\n\n"
    raw = preamble + MarkdownPlanBuilder("Test Plan").build()
    plan = parser.parse(raw)
    # Should parse without errors
    assert plan.title == "Test Plan"
    # Preamble should not appear in raw_content
    assert "Some text before the plan" not in plan.raw_content


def test_parser_strips_preamble_with_code_fence(parser: IPlanParser):
    """Preamble containing code fences should be stripped."""
    preamble = "```\ncode in preamble\n```\n\n"
    raw = preamble + MarkdownPlanBuilder("Test Plan").build()
    plan = parser.parse(raw)
    assert plan.title == "Test Plan"


def test_parser_strips_preamble_with_inline_hash(parser: IPlanParser):
    """Preamble with # inside text (not a heading) should be stripped."""
    preamble = "This has a # symbol but it's not a heading.\n\n"
    raw = preamble + MarkdownPlanBuilder("Test Plan").build()
    plan = parser.parse(raw)
    assert plan.title == "Test Plan"


def test_parser_handles_no_preamble_correctly(parser: IPlanParser):
    """Plan with no preamble should parse normally."""
    raw = MarkdownPlanBuilder("Test Plan").build()
    plan = parser.parse(raw)
    assert plan.title == "Test Plan"
    # raw_content should not have any extra prefix
    assert plan.raw_content.startswith("# Test Plan")


def test_parser_strips_preamble_with_only_whitespace(parser: IPlanParser):
    """Whitespace-only preamble before H1 should not cause issues."""
    preamble = "   \n\n  "
    raw = preamble + MarkdownPlanBuilder("Test Plan").build()
    plan = parser.parse(raw)
    assert plan.title == "Test Plan"
```

## Verification
1. [ ] All existing parser tests pass (no regressions).
2. [ ] All new preamble-stripping test cases pass.
3. [ ] Manual test: Preamble text in a plan payload does not appear in the final `plan.md`.
4. [ ] Manual test: Preamble text does not cause structural validation errors.
5. [ ] Run `git status` to verify only the planned files are modified.
