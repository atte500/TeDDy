# Slice: Fix Parser Nesting Bug

- **Status:** Completed
- **Milestone:** [08-core-refactoring-and-enhancements](/docs/project/milestones/08-core-refactoring-and-enhancements.md)
- **Spec:** [New Plan Format](/docs/project/specs/new-plan-format.md)

## 1. Business Goal & Interaction Sequence
**Goal:** To fix a critical bug where the `MarkdownPlanParser` accepts plans with invalidly nested code blocks (where the inner fence has the same number of backticks as the outer fence). This can lead to unpredictable parsing and silent data corruption. This fix reinforces the "Jidoka" (autonomation) principle by stopping this defect.

**Interaction:**
1.  **AI/User:** Submits a plan with an invalidly nested code block (e.g., a ` ` ` ` block inside another ` ` ` ` block).
2.  **System:** `MarkdownPlanParser` detects the structurally invalid sequence in the AST.
3.  **System:** Rejects the plan immediately, raising a clear `InvalidPlanError`.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: Rejecting Improperly Nested Fences
**Given** a Markdown plan where a code block is nested inside another using the same fence length
**When** the plan is parsed
**Then** the parser must reject the plan with an `InvalidPlanError`
**And** the error message should indicate an unexpected or malformed sequence was found.

**Example (Failing Case):**
A plan that attempts to create a file containing a code block whose fence is the same length as the fence for the `CREATE` action's content block.

``````markdown
# Plan to Create a Failing Plan

## Action Plan

### `CREATE`
- **File Path:** [failing_plan.md](/failing_plan.md)
- **Description:** Create a plan that has invalid nesting.
````markdown
# This is the inner plan that will be created
## Action Plan
### `EXECUTE`
- **Description:** A command.
````shell
echo "hello"
````
````
``````

### Scenario 2: Accepting Properly Nested Fences
**Given** a Markdown plan with a properly nested code block (e.g., 3 backticks inside 4)
**When** the plan is parsed
**Then** the parser must accept the plan
**And** all actions and content must be parsed correctly.

### Scenario 3: Regression Test for Interstitial Content
**Given** a Markdown plan that contains a `ThematicBreak` (`---`) or stray paragraph between two actions
**When** the plan is parsed
**Then** the parser must reject the plan with an `InvalidPlanError`.

## 3. Architectural Changes

### `MarkdownPlanParser` Refactor
The parser will be refactored to implement the validated "Single-Pass State Machine" algorithm. This aligns with the architectural decision for "Strict Parser Validation".

1.  **State Machine Logic:** The `_parse_actions` method will iterate through the flat list of top-level tokens produced by `mistletoe` after the `## Action Plan` heading.
2.  **Sequence Enforcement:** The logic must validate the sequence of tokens. It expects a repeating pattern of `(Action Heading, Action Content...)`.
3.  **Stray Content Rejection:** Any token that is not a valid action heading or recognized action content (e.g., `List`, `CodeFence`, `Heading` for `EDIT`) will be treated as a validation error. This explicitly rejects stray text (`Paragraph` tokens) or separators (`ThematicBreak`).
4.  **Malformed Sequence Rejection:** The parser must reject malformed sequences, such as two action headings in a row.

## 4. Scope of Work

1.  **Refactor `MarkdownPlanParser._parse_actions`:**
    -   Replace the current parsing loop with the new state machine logic as proven in the `spike_sequence_aware_parser.py` spike.
    -   Ensure it correctly identifies action headings (level-3 `Heading` with a single `InlineCode` child).
    -   Implement the strict sequence and content validation logic.
2.  **Harmonize Metadata Handling (Refactoring):**
    -   While refactoring, address the inconsistent handling of `Description` metadata across the various `_parse_*_action` methods, as noted in slice 09.
    -   Standardize the approach so all action parsers handle this metadata consistently.
3.  **Update Unit Tests (`tests/unit/core/services/test_markdown_plan_parser.py`):**
    -   Add a new test case, `test_rejects_improperly_nested_code_fences`, using the MRE's invalid plan.
    -   Add a new test case, `test_accepts_properly_nested_code_fences`.
    -   Ensure the existing test `test_parse_plan_with_interstitial_content_fails` still passes.
    -   Verify all other existing parser tests pass after the refactor.

## Implementation Summary
- **Strict Document Validation:** Implemented `_parse_strict_top_level` to enforce an exact sequence of `H1`, Metadata `List`, `H2` Rationale, `CodeBlock`/`CodeFence`, (optional Memos), and `H2` Action Plan.
- **Actionable AST Diffs:** Added `_raise_structural_error` to provide high-fidelity, actionable feedback (including AST node differences and code fence nesting hints) when validation fails, directly supporting the "Automated Re-plan Loop".
- **Action Sequence Enforcement:** Updated `_parse_actions` to require exactly an `H3` Action heading, instantly failing on stray interstitial content.
- **Metadata Harmonization:** Centralized the extraction of `Description` metadata across all action types using `_parse_action_metadata`.
