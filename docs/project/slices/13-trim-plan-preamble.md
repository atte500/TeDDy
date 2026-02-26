# Slice 13: Trim Plan Preamble

## Business Goal

To improve the robustness and usability of the plan parser by making it ignore any "preamble" text that may appear before the main Level 1 heading (`# Plan Title`). This prevents validation errors from accidentally included content (e.g., from copy-paste operations) and ensures only the valid plan content is processed.

## Acceptance Criteria

### Scenario 1: Plan with Preamble is Parsed Successfully
```gherkin
Given a Markdown plan file that contains text before the "# Plan Title" heading
When the `teddy execute` command is run against the plan
Then the plan is parsed and executed successfully
And the preamble text is ignored
```
**Example:**
```markdown
This is some preamble text.
It should be ignored by the parser.

# Plan Title
- Status: Green 🟢
...
```

### Scenario 2: Standard Plan Parses Correctly
```gherkin
Given a valid Markdown plan file that starts immediately with the "# Plan Title" heading
When the `teddy execute` command is run against the plan
Then the plan is parsed and executed successfully
```

### Scenario 3: Plan without a Title Fails Validation
```gherkin
Given a Markdown file that contains text but no Level 1 heading
When the `teddy execute` command is run against the plan
Then the command fails with a validation error indicating that a plan title could not be found
```

## Architectural Changes

- **Component to Modify:** `MarkdownPlanParser`
- **File:** `src/teddy_executor/core/services/markdown_plan_parser.py`

The core parsing logic within this service must be updated to find the first `H1` token and treat all preceding tokens as preamble to be discarded.

## Scope of Work

- [x] Modify the `parse` method in `src/teddy_executor/core/services/markdown_plan_parser.py`.
- [x] Update the logic to iterate through the initial tokens of the AST, discard them until the first `mistletoe.block_token.Heading` of `level=1` is found, and then begin parsing from that point.
- [x] If no Level 1 Heading is found in the document, raise a `PlanParsingError` to maintain existing validation behavior for plans without titles.
- [x] Create a new acceptance test file (e.g., `tests/acceptance/test_parser_robustness.py`).
- [x] Add tests to this file that cover all scenarios outlined in the Acceptance Criteria.
- [x] Ensure all existing unit, integration, and acceptance tests continue to pass.

## Implementation Summary

This slice was implemented following a strict outside-in TDD workflow.

1.  **Outer RED:** A new acceptance test file, `tests/acceptance/test_parser_robustness.py`, was created with a single failing test (`test_plan_with_preamble_is_parsed_successfully`) to act as the North Star.
2.  **Inner TDD Loop:**
    *   **RED:** A new failing unit test, `test_parse_succeeds_with_preamble_before_title`, was added to `tests/unit/core/services/test_markdown_plan_parser.py`.
    *   **GREEN:** The `_parse_strict_top_level` method in `MarkdownPlanParser` was modified to iterate past any preamble tokens until it found the first H1 heading.
    *   **REFACTOR:** The change introduced a regression in an existing test that asserted the old behavior. This obsolete test was removed. The parser logic was further refined to explicitly raise an error if no H1 heading is found at all, and a new unit test was added to cover this case.
3.  **Outer GREEN:** The guiding acceptance test was run again and passed. Additional acceptance tests were added to cover the remaining scenarios (standard plan and no-title plan), which also passed.
4.  **Polish & Commit:** The code was cleaned up, and the final implementation was committed as a single atomic unit.

There were no significant deviations from the plan, and no new refactoring opportunities were identified.
