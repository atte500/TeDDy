# Milestone 08: Refactor to a Robust, AST-Based Plan Parser

## 1. Goal (The "Why")

The current `MarkdownPlanParser` is brittle and fails to parse valid plans if the content of a code block (e.g., in an `EDIT` action) contains text that resembles a Markdown structural element (like `---` or `### ACTION`). This is a critical bug that prevents agents from reliably editing a wide range of documents.

-   **Referenced Specification:** [Spec: Robust Plan Parsing](./../specs/robust-plan-parsing.md)

## 2. Proposed Solution (The "What")

We will refactor the `MarkdownPlanParser` to use a robust, single-pass AST traversal strategy. The current implementation's multi-pass approach, which separates identifying headings from validating structure, is the source of the fragility. The new approach will parse each action and its content as a single, atomic unit.

## 3. Implementation Guidelines (The "How")

The refactor will replace the core parsing logic with a new algorithm that traverses the AST more intelligently.

### 3.1. The Single-Pass Traversal Algorithm

The core `_parse_actions` method should be re-implemented to follow this logic:

1.  Locate the `## Action Plan` heading node in the `mistletoe` document's children.
2.  Create a "stream" or iterator of all subsequent sibling nodes.
3.  Loop through this stream:
    a. Check if the current node is a valid action heading (`Heading`, level 3, with `InlineCode` like `` `ACTION` ``).
    b. **If it is an action heading:**
       i.  Determine the `action_type`.
       ii. Delegate to a dedicated parsing method for that type (e.g., `_parse_edit_action`).
       iii. This dedicated method is now responsible for consuming nodes from the *same shared stream* until it has fully parsed its content. It stops consuming when it encounters the next action heading or a section heading (H1/H2), leaving that node in the stream for the main loop to process next.
    c. **If it is not an action heading:** This is an invalid state (e.g., free text between actions). The parser should raise an `InvalidPlanError`.
4.  This approach ensures that the content of one action (like the code blocks in `EDIT`) is consumed entirely by its dedicated parser and is never seen by the main loop, eliminating the bug.

### 3.2. Other Requirements

-   The fragile `_validate_action_structure` method must be removed. Its function is now implicitly and more robustly handled by the new traversal algorithm.
-   The `_find_action_headings` method should be removed or repurposed as it is part of the old, flawed strategy.

3.  **Testing Requirements:**
    -   A new unit test must be added to `tests/unit/core/services/test_markdown_plan_parser.py` that uses the verbatim failing plan from the user's bug report. This test will serve as the primary regression guard.
    -   All existing unit tests for the parser must continue to pass.

## 4. Acceptance Criteria

-   The user-reported failing plan is parsed successfully.
-   The refactored `MarkdownPlanParser` correctly parses all plans that were valid under the old implementation.
-   The new implementation is demonstrably more resilient to arbitrary content within action code blocks.

## 5. Vertical Slices

1.  **Slice 1: Refactor Parser and Fix Bug**
    -   Implement the new single-pass parsing strategy in `MarkdownPlanParser`.
    -   Add the new regression test case.
    -   Ensure all existing tests pass.
