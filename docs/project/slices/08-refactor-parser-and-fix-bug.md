# Slice: Refactor Parser and Fix Bug

- **Status:** Complete
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

## Implementation Summary

This slice was implemented to fix a bug where interstitial content (like a `---` thematic break) between actions would cause the `MarkdownPlanParser` to crash.

### Key Changes
1.  **Requirement Pivot:** The initial goal was to make the parser robustly *ignore* such content. After discussion, this was pivoted to a stricter requirement: the parser must *reject* any plan with unexpected content between actions. This aligns better with the project's "fail-fast" and "contract-first" principles.
2.  **Parser Refactoring:** The `MarkdownPlanParser` was modified to remove the logic that ignored `ThematicBreak`s, causing it to correctly raise an `InvalidPlanError`.
3.  **Orchestrator Refactoring:** A significant amount of work involved addressing a `T2` architectural note. The `ExecutionOrchestrator`'s contract was changed to accept a parsed `Plan` object instead of a raw string. This eliminated redundant parsing within the `CLIAdapter` (`main.py`) and clarified the separation of concerns between parsing and execution. This required updating the `RunPlanUseCase` interface and refactoring numerous unit and integration tests.
4.  **Debugger Handoff:** A persistent `SystemExit(2)` crash during testing was misdiagnosed as an application bug. After two failed fix attempts, a handoff to the `Debugger` correctly identified the root cause as a faulty acceptance test using an invalid CLI flag. This unblocked the slice and highlighted the value of the escalation protocol.

### Architectural Notes Log
- **T1 (Pre-existing Condition):** The initial requirement for the parser to ignore thematic breaks was incorrect. The new requirement is to treat them as a validation error. This pivot was directed by the user. (Formalized in `ARCHITECTURE.md`)
- **T4 (True Blocker):** An unhandled exception in the CLI adapter caused a silent crash. (Resolved by Debugger: issue was a faulty test.)
- **T2 (Slice-Refactor):** The `execute` command in `main.py` parsed the plan twice. (Resolved by refactoring the orchestrator contract.)
