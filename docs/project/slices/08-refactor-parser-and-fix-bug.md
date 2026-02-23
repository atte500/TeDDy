# Slice: Refactor Parser and Fix Bug

- **Status:** Planned
- **Milestone:** [08-core-refactoring-and-enhancements](/docs/project/milestones/08-core-refactoring-and-enhancements.md)
- **Spec:** [Robust Plan Parsing](/docs/project/specs/robust-plan-parsing.md)

## 1. Business Goal & Interaction Sequence
**Goal:** To enable the AI to reliably edit complex Markdown files (including other plans and specs) by refactoring the `MarkdownPlanParser` to support nested code blocks. This fixes a critical "Jidoka" failure where valid plans cause system crashes.

**Interaction:**
1.  **AI/User:** Submits a plan containing an `EDIT` action where the content includes fenced code blocks (e.g., editing a Markdown file).
2.  **System:** `MarkdownPlanParser` correctly identifies the outer action boundary, ignoring the nested fences.
3.  **System:** Validates and executes the plan successfully.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: Rejecting Invalid Separators
**Given** a Markdown plan that contains a `ThematicBreak` (horizontal rule `---`) between two actions
**When** the plan is parsed
**Then** the parser must reject the plan
**And** a validation error must be raised indicating that `ThematicBreak` is not a valid separator between actions.

**Example (Failing Case - Thematic Break):**
````````markdown
# Failing Plan (Thematic Break)

### `EDIT`
- **File Path:** [docs/doc.md](/docs/doc.md)
- **Description:** Add a separator.

#### `FIND:`
````markdown
End of section.
````
#### `REPLACE:`
````markdown
End of section.

---

Start of new section.
````
````````

### Scenario 2: Parsing Nested Code Blocks (Regression Test)
**Given** a Markdown plan that contains an `EDIT` action with complex nested code blocks (e.g., 3 backticks inside 4)
**When** the plan is parsed
**Then** the parser must correctly identify the `EDIT` action
**And** the content of the nested blocks must be preserved verbatim.

*Note: While `mistletoe` handles this correctly in isolation, the refactored parser must ensure this capability is preserved.*

### Scenario 3: Regression Testing Standard Plans
**Given** a standard plan with multiple actions (`CREATE`, `EXECUTE`, `CHAT_WITH_USER`)
**When** the plan is parsed
**Then** all actions are correctly identified
**And** all arguments are correctly extracted.

## 3. User Showcase
*To verify this fix manually:*

1.  Create a file named `repro_plan.md` with the content from "Scenario 1".
2.  Run `teddy execute --plan-content "$(cat repro_plan.md)"`.
3.  **Success:** The system parses the plan (it might fail execution if files don't exist, but it **must not** crash with a parsing error).

## 4. Architectural Changes

### `MarkdownPlanParser` Refactor
The parser will be refactored to provide clearer error messages for invalid plan structures.

1.  **Strict Structural Validation:** The parser will iterate through the document's `## Action Plan` section and validate that only known action headings (`### `...``) and their content are present.
2.  **Enforced Separation:** Any content between valid action blocks, such as a `ThematicBreak` (`---`) or stray paragraphs, will be treated as a validation error.
3.  **Clear Error Reporting:** The error message must clearly state which unexpected content was found (e.g., `ThematicBreak`) and that it is not permitted between actions.
4.  **`_get_text(node)` Helper:** A robust recursive helper to extract text from `mistletoe` tokens, prioritizing `children` (for spans) over `content` (for raw text), fixing the `InlineCode` access bug, will be preserved or implemented.

## 5. Scope of Work

1.  **Refactor `MarkdownPlanParser`:**
    -   Implement `PeekableStream` class.
    -   Implement recursive `_get_text` helper.
    -   Rewrite `parse` loop to use the stream and dispatch strategy.
    -   Rewrite all `_parse_*_action` methods to consume from the stream.
    -   Remove obsolete validation logic (`_validate_action_structure`, `_find_action_headings`).
2.  **Update Unit Tests:**
    -   Ensure `test_markdown_plan_parser.py` passes with the new implementation.
    -   Add new test case: `test_parse_plan_with_interstitial_content` (verifying `ThematicBreak` is ignored).
3.  **Verify Fix:**
    -   Run the MRE `spikes/mre/parser_break_repro.py` against the *refactored* code (after moving/adapting it or creating a new test) to confirm the crash is gone.
