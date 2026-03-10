# Slice: Validation & Diagnostics Polish

- **Status:** Planned
- **Milestone:** N/A (Fast-Track)
- **Specs:** N/A

## 1. Business Goal

Improve the developer experience (DX) and reliability of plan execution by providing clearer, more actionable error messages and diagnostics when plan validation fails. This slice addresses three specific, low-friction polishing items that significantly reduce the cognitive load required to debug malformed plans.

## 2. Acceptance Criteria (Scenarios)

### Scenario A: Correct Placement of Mismatch Indicator in AST Trace

**Given** a plan with an `EDIT` action containing a `FIND` block but missing the subsequent `REPLACE` block,
**When** the plan is validated,
**Then** the resulting validation error message should state "Missing REPLACE block after FIND block" without appending the mismatch indicator directly to the error message text.
**And** the AST Summary trace should correctly append the `<-- MISMATCH` indicator to the exact AST node that broke the expected sequence (e.g., the paragraph that appeared instead of the `REPLACE` heading).

#### Deliverables
- [ ] Remove `MISMATCH_INDICATOR` from the hardcoded error strings in `action_parser_strategies.py`.
- [ ] Ensure the parsing error correctly passes the `actual_node` to the structural mismatch formatter so the indicator appears on the correct node in the trace.
- [ ] Acceptance test verifying the exact format of the error message and AST trace for this scenario.

### Scenario B: Helpful Hint for Multiple FIND Matches

**Given** a plan with an `EDIT` action where the `FIND` block matches multiple identical snippets in the target file,
**When** the plan is validated,
**Then** the validation error message should not only indicate that multiple matches were found, but also include a clear hint: "Hint: Consider refactoring the target code or providing a larger FIND block to uniquely identify the section."

#### Deliverables
- [ ] Update the validation logic (likely in `validation_rules/edit.py` or the `edit_simulator.py` exception handling) to append the hint to the multiple matches error message.
- [ ] Acceptance test verifying the presence of the hint in the validation output.

### Scenario C: Backtick Count in AST Summary for Code Fences

**Given** a plan containing a fenced code block,
**When** the plan fails validation and an AST Summary trace is generated,
**Then** the entry in the trace for that code block should explicitly include the number of backticks used in its fence (e.g., `[NNN] CodeFence (5 backticks)`).

#### Deliverables
- [ ] Modify the node formatting logic in `markdown_plan_parser.py` (or `parser_infrastructure.py`) to inspect `FencedCode` nodes.
- [ ] Extract the length of the node's `marker` property (which represents the backtick sequence) and append it to the formatted node name.
- [ ] Acceptance test verifying the correct format of the `CodeFence` entry in the AST trace.

## 3. Architectural Changes

This slice entirely resides within the parsing and validation layers. No new components are introduced.

-   **`src/teddy_executor/core/services/action_parser_strategies.py`**:
    -   Remove the appending of `MISMATCH_INDICATOR` to the string in the "Missing REPLACE block" error handling. Ensure the `ParseError` is constructed correctly so the AST formatter handles the indicator.
-   **`src/teddy_executor/core/services/markdown_plan_parser.py`**:
    -   Update `_format_structural_mismatch_msg` (or its helper functions) to inspect AST nodes when building the trace. If a node is an instance of `marko.block.FencedCode`, read `node.marker` (or the equivalent property for the fence string) and format the output as `CodeFence (X backticks)`.
-   **`src/teddy_executor/core/services/validation_rules/edit.py`** (or `edit_simulator.py`):
    -   Update the error message returned when an edit fails due to multiple matches to include the required hint.
