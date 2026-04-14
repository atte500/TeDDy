# Vertical Slice: EDIT Indentation Refinement & Threshold

- **Status:** Planned
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Specs:** [plan-format](../../specs/plan-format.md)
- **Prototype:** [prototypes/edit_indentation_spike.py]
- **Component Docs:** [edit-simulator](../../architecture/core/services/edit_simulator.md)
- **Internal Specs:**
  - [src/teddy_executor/core/services/validation_rules/edit_matcher.py](/src/teddy_executor/core/services/validation_rules/edit_matcher.py)
  - [src/teddy_executor/core/domain/models/plan.py](/src/teddy_executor/core/domain/models/plan.py)
  - [src/teddy_executor/core/services/edit_simulator.py](/src/teddy_executor/core/services/edit_simulator.py)

## Business Goal
Improve the robustness of the `EDIT` action by allowing agents to provide `FIND` blocks with inconsistent indentation (as long as the relative indentation is correct) and increasing the strictness of content matching.

## Scenarios
> As a Developer, I want the EDIT action to match blocks even if I mis-indented them relative to the file, so that I don't have to worry about exact whitespace alignment as long as the code structure is correct.

### Scenario 1: Match with Relative Indentation
Given a file with 4-space indentation
When an EDIT action provides a FIND block with 2-space indentation (but matching content structure)
Then the block should match
And the REPLACE block should be applied with the file's 4-space indentation.

### Scenario 2: Strict Content Matching
Given the improved indentation handling
Then the default similarity threshold should be 1.00 (exact content match, ignoring relative indentation).

### Deliverables
- [ ] **Logic** - Implement relative indentation detection and normalization in `EditMatcher.find_best_match`.
- [ ] **Logic** - Ensure `EditSimulator` receives and applies the detected indentation offset to the `REPLACE` block.
- [ ] **Logic** - Set `DEFAULT_SIMILARITY_THRESHOLD` to 1.00 in `src/teddy_executor/core/domain/models/plan.py`.
- [ ] **Harness** - Add unit tests in `tests/suites/unit/core/services/test_edit_matcher_indentation.py` (new file) to verify relative indentation handling.

## Guidelines for Implementation

### Indentation-Agnostic Matching Logic
The core improvement should be implemented in `src/teddy_executor/core/services/validation_rules/edit_matcher.py` within the `_refine_and_select_best` function.

1.  **Normalization:** Maintain existing trailing whitespace normalization (`rstrip`).
2.  **Offset Detection:**
    - For each line in the candidate window and `FIND` block:
        - Verify `trimmed_window == trimmed_find`.
        - Calculate `offset = window_indent - find_indent`.
    - If all non-empty lines have the same `offset`, treat the match as a `1.0` ratio.
3.  **Replacement Adjustment:**
    - Return the `offset` to `EditSimulator._apply_single_edit`.
    - Apply the `offset` to every non-empty line of the `REPLACE` block before performing the final string substitution.

### Threshold Update
Update `DEFAULT_SIMILARITY_THRESHOLD` to `1.00` in `src/teddy_executor/core/domain/models/plan.py`. This ensures that we only match exact code logic, while remaining flexible to the agent's indentation formatting.
