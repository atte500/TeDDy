# Report Format Specification

## 1. Overview and Core Principles

This document specifies the format for `report.md`. This report is a multi-purpose, foundational artifact in the Teddy workflow, designed with three core principles in mind:

1.  **A Factual Record of the Past:** It serves as an immutable, factual log of what occurred during the execution of a `plan.md`. It details which actions were approved, which were skipped, and the precise outcome of each.
2.  **The Worldview for the Future:** It provides the AI with its complete, single-source-of-truth "worldview" for the *next* turn. By containing a full snapshot of the project's state *after* the execution, it serves as the primary input for the next planning phase.
3.  **Human & Machine Readable:** The format is Markdown-first, providing a clear, readable document for humans while maintaining a strict, parsable structure for tooling and AI consumption.

## 2. Overall Document Structure

A report is a single Markdown file with three main sections:

```markdown
# Execution Report: [Original Plan Title]
- **Overall Status:** [Completed | Partial | Failed | Skipped]
- **Original Plan:** [path/to/original/plan.md](/path/to/original/plan.md)
...

## 1. Rationale
... (The "Why" - Copied from the original plan)

## 2. Execution Summary
... (The "What Happened" - The log of actions and outcomes)

## 3. Workspace Snapshot
... (The "What Now" - The state of the project for the next turn)
```

---

## 3. Section Specifications

### 3.1. Report Header

-   **Purpose:** Contains the report's title and high-level summary metadata about the execution phase.
-   **Format:**
    ```markdown
    # Execution Report: Research and Propose a New "Finisher" Agent Role
    - **Overall Status:** Partial 🟡
    - **Original Plan:** [01/plan.md](/01/plan.md)
    - **Start Time:** 2023-10-27T10:00:00.123Z
    - **End Time:** 2023-10-27T10:00:05.567Z
    - **Actions:** 5 Total / 4 Approved / 1 Skipped
    - **Outcomes:** 3 Succeeded / 1 Failed
    - **User Prompt:** (Optional) "I did not implement the EDIT because I feel it's redundant, please proceed without it."
    ```

### 3.2. Section 1: Rationale

-   **Purpose:** Provides the AI with the essential context of *why* the previous turn's actions were attempted.
-   **Content:** This section contains the verbatim, unchanged `Rationale` block copied directly from the `plan.md` that was executed.
-   **Format:**
    `````markdown
    ## 1. Rationale
    ````text
    Observation: The user has requested a new "Finisher" agent role...
    Analysis: This requires a discovery process...
    Next Step: ...
    ````
    `````

### 3.3. Section 2: Execution Summary

-   **Purpose:** A detailed, factual log of what happened during plan execution. This section's structure intentionally mirrors the `Action Plan` of the original `plan.md` for easy comparison.
-   **Content:** It contains subsections for `Applied State Changes` and the `Action Log`.
-   **Format:**
    `````markdown
    ## 2. Execution Summary

    ### Applied State Changes
    ...

    ### Action Log
    ...
    `````
-   **Subsection: Applied State Changes**
    -   Confirms which proposed changes to `Active Context` and `Memos` were approved and applied.
    -   Each state change type (`Active Context`, `Memos`) gets its own `####` heading, a status, and a code block showing the proposed change from the plan.
-   **Subsection: Action Log**
    -   Provides an action-by-action breakdown. Each action from the plan is represented by its own `####` heading.
    -   **Crucially, each action block in the report preserves the complete, verbatim metadata list (e.g., `File Path`, `Description`, `Expected Outcome`, `cwd`, `env`) from the original plan.** This ensures a direct, one-to-one mapping between the plan and the report.
    -   Every action must have a **Status** (`Approved ✅` or `Skipped 🟡`).
    -   Approved actions must have an **Execution** status (`Success 🟢` or `Failure 🔴`) and may include an `Execution Details` block with outputs or errors.

### 3.4. Section 3: Workspace Snapshot

-   **Purpose:** Provides the AI with a complete and comprehensive snapshot of the project's state *after* the turn's execution. This section serves as the primary input for the AI's next planning phase.
-   **Content:** It is composed of several subsections that give the AI a full picture of the environment, project structure, and file contents.

#### 3.4.1. System Information
A simple key-value list of essential environment details.
- **Example:**
  ```markdown
  #### 1. System Information
  - **CWD:** /Users/developer/projects/TeDDy
  - **OS:** Darwin 25.2.0
  ```

#### 3.4.2. Project Structure
A textual representation of the repository's file tree.
- **Example:**
  `````markdown
  #### 2. Project Structure
  ````
  .
  ├── .teddy/
  └── docs/
      └── specs/
          └── report-format.md
  ````
  `````

#### 3.4.3. Memos
The verbatim content of the `.teddy/memos.yaml` file.
- **Example:**
  `````markdown
  #### 3. Memos
  ````
  - A new 'Finisher' agent role is being explored.
  ````
  `````

#### 3.4.4. Turn Context
-   **Purpose:** Lists the file paths from the current turn's `turn.context` file. This represents the dynamic part of the AI's context—the "working set" that it can modify from turn to turn via the `Active Context` block in its plans.
-   **Example:**
    `````markdown
    #### 4. Turn Context
    ````
    - docs/specs/interactive-session-workflow.md
    ````
    `````

#### 3.4.5. Resource Contents
-   **Purpose:** The full, verbatim content of every resource from the combined context.
-   **Sourcing:** The list of resources is aggregated from `.teddy/global.context`, the session-specific `<session>/session.context`, and the current turn's `turn.context`. This provides the AI with a complete view of all relevant files.
- **Example:**
  `````markdown
  #### 5. Resource Contents

  ---
  **Resource:** `[docs/specs/report-format.md](/docs/specs/report-format.md)`
  ````markdown
  # Report Format Specification
  ... (full file content) ...
  ````
  ---
  `````

## 4. Comprehensive Example

``````markdown
# Execution Report: A New Report Format
- **Overall Status:** Completed 🟢
- **Original Plan:** [01/plan.md](/01/plan.md)
- **Start Time:** 2023-10-27T10:00:00.123Z
- **End Time:** 2023-10-27T10:00:05.567Z
- **Actions:** 1 Total / 1 Approved / 0 Skipped
- **Outcomes:** 1 Succeeded / 0 Failed
- **User Prompt:** "Your previous changes were good, but please add a section for the user prompt and clarify the action log metadata rule."

## 1. Rationale
````text
Observation: The user wants to refactor the report format.
Analysis: I need to perform a full-file replacement of `docs/specs/report-format.md`.
Next Step: Execute the `EDIT` action.
````

## 2. Execution Summary

### Applied State Changes
*(No state changes were proposed in the plan.)*

### Action Log

#### `EDIT`
- **Status:** Approved ✅
- **Execution:** Success 🟢
- **Duration:** 15ms
- **File Path:** [docs/specs/report-format.md](/docs/specs/report-format.md)
- **Description:** Overhaul the report format specification.
- **Expected Outcome:** The file should be updated with the new three-part structure.

## 3. Workspace Snapshot

### 1. System Information
- **CWD:** /Users/developer/projects/TeDDy
- **OS:** Darwin 25.2.0

### 2. Project Structure
````
.
├── .teddy/
└── docs/
    └── specs/
        └── report-format.md
````

### 3. Memos
````
- A new 'Finisher' agent role is being explored.
````

### 4. Turn Context
````
- docs/specs/report-format.md
````

### 5. Resource Contents

---
**Resource:** `[docs/specs/report-format.md](/docs/specs/report-format.md)`
````markdown
# Report Format Specification

## 1. Overview and Core Principles
... (full, new content of this file) ...
````
---
``````
