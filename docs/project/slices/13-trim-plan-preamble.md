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

- [ ] Modify the `parse` method in `src/teddy_executor/core/services/markdown_plan_parser.py`.
- [ ] Update the logic to iterate through the initial tokens of the AST, discard them until the first `mistletoe.block_token.Heading` of `level=1` is found, and then begin parsing from that point.
- [ ] If no Level 1 Heading is found in the document, raise a `PlanParsingError` to maintain existing validation behavior for plans without titles.
- [ ] Create a new acceptance test file (e.g., `tests/acceptance/test_parser_robustness.py`).
- [ ] Add tests to this file that cover all scenarios outlined in the Acceptance Criteria.
- [ ] Ensure all existing unit, integration, and acceptance tests continue to pass.
