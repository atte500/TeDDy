# Slice: Strip Preamble Before H1 in Plan Parser
- **Status:** Completed
- **Type:** Tweak
- **Milestone:** [Milestone 2: Stability & Infrastructure](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [Task: Strip Preamble Before H1](/docs/project/tasks/21-strip-preamble-before-h1.md)
- **Component Docs:** [MarkdownPlanParser](/docs/architecture/core/services/markdown_plan_parser.md)

## Business Goal
Prevent preamble text (any content before the first `#` heading in a plan payload) from causing structural validation errors and from appearing in the final parsed `plan.md`. Preamble text should be silently stripped during parsing.

## Scenarios
> As a Developer, I want preamble text before the first H1 heading to be silently stripped
> so that plans with unexpected introductory content still parse correctly.

```gherkin
Given a plan payload with preamble text before the first # heading
When the parser processes the payload
Then the preamble text is silently removed
And the plan parses without errors
And the preamble text does not appear in the parsed plan's raw_content
```

## Edge Cases
- **Preamble with code fences**: If preamble contains code fences, they should be stripped without affecting the actual action code blocks.
- **Preamble with inline hash symbols**: `#` inside preamble text (not a heading) should be correctly handled; the regex matches only H1 at line start.
- **No preamble**: Plans without any preamble should continue to parse normally.
- **Whitespace-only preamble**: Spaces and newlines before H1 should not cause issues.
- **H2 headings (## )**: The stripping must not accidentally match H2 headings; the regex `(?:^|\n)# (?!#)` ensures only H1 is matched.

## Deliverables
- [x] **Contract/Logic** - Add preamble stripping logic to `MarkdownPlanParser.parse()`.

## Implementation Notes
- **Bug discovered**: The initial approach used `clean_content.find("# ")` which incorrectly matched `##` in H2 headings (e.g., `"## Just a Sub-heading"` would match at position 1, stripping the H2 to become an H1). Fixed with regex `r"(?:^|\n)# (?!#)"` that only matches `# ` at line start, not preceded by another `#`.
- **Bug discovered**: The `raw_content` property was using the original `plan_content` instead of the stripped `clean_content`, causing preamble text to still appear in the parsed plan. Fixed by changing `raw_content=plan_content` to `raw_content=clean_content`.
- **Test creation issue**: The initial tests used `MarkdownPlanBuilder("Test Plan").build()` which produces a plan without actions, causing `Plan.__post_init__` assertion failure (`assert self.actions`). Fixed by using `_b().add_read("r.md").build()` to include at least one action.
- **Regex explanation**: The regex `(?:^|\n)# (?!#)` matches `# ` (H1) only at the start of a line (beginning of string or after a newline), and uses negative lookahead `(?!#)` to ensure it's not `## ` (H2).
- **Edge case handling**: If the match starts with `\n` (text before H1 after a blank line), the offset is incremented by 1 to skip the newline character itself, ensuring the stripping is clean.

## Implementation Plan
1. In `markdown_plan_parser.py`; `parse()` method: Add `import re`; inject preamble stripping after `clean_content.rstrip()` and before preprocessor; replace `raw_content=plan_content` with `raw_content=clean_content`.
2. In `test_parser_errors.py`: Add 5 test cases covering preamble text, code fences, inline hash, no preamble, whitespace-only.
