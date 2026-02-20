# Spec: Robust Plan Parsing

## 1. The Problem (The "Why")

The current `MarkdownPlanParser` service fails to parse valid plans that contain action definitions (e.g., `### CREATE`) inside the fenced code blocks of an `EDIT` action. The parser incorrectly interprets these nested code snippets as top-level actions, leading to validation failures.

This is a critical flaw that prevents agents from editing documentation, specifications, or other plans, severely limiting the system's capabilities.

### 1.1. Verifiable Failure Case

The following plan reliably reproduces the bug. The parser fails with an "Unexpected content found between actions" error.

``````markdown
# Verbatim Failing Plan

### `EDIT`
- **File Path:** [docs/project/specs/new-plan-format.md](/docs/project/specs/new-plan-format.md)
- **Description:** Update functional links and illustrative examples.

#### `FIND:`
````markdown
### 5.1. `CREATE`

-   **Purpose:** Creates a new file.
-   **Format:**
    `````markdown
    ### `CREATE`
    - **File Path:** [docs/specs/plan-format.md](/docs/specs/plan-format.md)
    - **Description:** Create the initial specification document.
`````
````
#### `REPLACE:`
````markdown
### 5.1. `CREATE`

-   **Purpose:** Creates a new file.
-   **Format:**
    `````markdown
    ### `CREATE`
    - **File Path:** [docs/project/specs/plan-format.md](/docs/project/specs/plan-format.md)
    - **Description:** Create the initial specification document.
`````
````
``````

## 2. Acceptance Criteria

-   The `MarkdownPlanParser` MUST be refactored to correctly parse the "Verifiable Failure Case" plan without errors.
-   The solution MUST be robust enough to distinguish between top-level `### Action` headings and identical text within any fenced code block.
-   The new implementation MUST NOT break parsing for existing, simpler plans.
