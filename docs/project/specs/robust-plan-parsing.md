# Spec: Robust Plan Parsing

## 1. The Problem (The "Why")

The current `MarkdownPlanParser` service fails to parse valid plans that contain action definitions (e.g., `### CREATE`) inside the fenced code blocks of an `EDIT` action. The parser incorrectly interprets these nested code snippets as top-level actions, leading to validation failures.

This is a critical flaw that prevents agents from editing documentation, specifications, or other plans, severely limiting the system's capabilities.

### 1.1. Verifiable Failure Cases

The current parser validation logic strictly whitelists allowed Markdown nodes (Lists, Code Blocks, Headings) within an action. It fails if it encounters valid Markdown content like horizontal rules (`---`) or nested code blocks that confuse the structure.

#### Case 1: Thematic Break (Horizontal Rule)
The parser treats `---` as a `ThematicBreak` node, which is not in the allowed whitelist, causing an immediate crash.

`````markdown
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
`````

#### Case 2: Nested Code Blocks (Potential Edge Case)
While the parser theoretically struggles with ambiguous nesting (e.g., three backticks inside three backticks), current tests suggest `mistletoe` handles standard nesting correctly. However, a robust parser should not rely on this library behavior and should explicitly handle stream consumption to prevent future regressions where nested content might leak into the top-level structure.

## 2. Acceptance Criteria

-   The `MarkdownPlanParser` MUST be refactored to correctly parse the "Verifiable Failure Case" plan without errors.
-   The solution MUST be robust enough to distinguish between top-level `### Action` headings and identical text within any fenced code block.
-   The new implementation MUST NOT break parsing for existing, simpler plans.
