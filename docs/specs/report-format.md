# Report Format Specification

## 1. Overview and Core Principles

This document specifies the format for `report.md`. This report is a multi-purpose, foundational artifact in the Teddy workflow, designed with three core principles in mind:

1.  **A Factual, Historical Record:** It serves as an immutable, factual log of what occurred during the execution of a `plan.md`. It details which actions were approved, which were skipped, and the precise outcome of each. Crucially, it is a purely historical document and has no direct influence on the context of future turns.
2.  **Human & Machine Readable:** The format is Markdown-first, providing a clear, readable document for humans while maintaining a strict, parsable structure for tooling and AI consumption.

### 1.2. Report Formats: Rich vs. Concise

The system uses a single, canonical report data model that can be rendered into two distinct formats to support different workflows:

1.  **Rich Report (this document):** This specification defines the **Rich Report**. It is a verbose, file-based artifact (`report.md`) designed for the stateful, interactive session workflow. Its purpose is to be a complete, auditable historical record, including verbatim content from the original plan.
2.  **Concise Report (CLI Output):** This is a compact rendering of the same data, optimized for the manual, chat-based workflow. Its specific format is defined in the [Concise Report Format Specification](./concise-report-format.md).

## 2. Overall Document Structure

A report is a single Markdown file with three main sections: the Report Header, the Original Plan Details, and the Execution Summary.

```markdown
# Execution Report: [Original Plan Title]
- **Overall Status:** [Completed | Partial | Failed | Skipped]
- **Original Plan:** [path/to/original/plan.md](/path/to/original/plan.md)
...

## 1. Original Plan Details
### Header
... (The verbatim header from the plan)
### Rationale
... (The verbatim rationale from the plan)

## 2. Execution Summary
... (The "What Happened" - The log of actions and outcomes)
```

---

## 3. Section Specifications

### 3.1. Report Header & Summary

-   **Purpose:** Provides a high-level summary of the execution phase itself.
-   **Format:**
    ````markdown
    # Execution Report: [Original Plan Title]
    - **Overall Status:** Partial 🟡
    - **Original Plan:** [01/plan.md](/01/plan.md)
    - **Execution Start Time:** 2023-10-27T10:00:00.123Z
    - **Execution End Time:** 2023-10-27T10:00:05.567Z
    - **Actions:** 5 Total / 4 Approved / 1 Skipped
    - **Outcomes:** 3 Succeeded / 1 Failed
    - **User Prompt:** (Optional) "I did not implement the EDIT because I feel it's redundant, please proceed without it."
    ````

### 3.2. Section 1: Original Plan Details

-   **Purpose:** Provides the AI with the complete context of the original plan.
-   **Content:** This section contains the verbatim, unchanged header (Title, Status, Agent, etc.) and the full `Rationale` block copied directly from the `plan.md` that was executed. This ensures zero context loss.
-   **Format:**
    ````markdown
    ## 1. Original Plan Details

    ### Header
    ````markdown
    # [Original Plan Title]
    - **Status:** [Original Status]
    - **Plan Type:** [Original Plan Type]
    - **Agent:** [Original Agent]
    ````

    ### Rationale
    ... (The verbatim "Rationale" block from the plan)
    ````
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
-   **Content:** It contains an `Action Log` which provides an action-by-action breakdown of the execution.
-   **Format:**
    `````markdown
    ## 2. Execution Summary

    ### Action Log
    ...
    `````
-   **Subsection: Action Log**
    -   Provides an action-by-action breakdown. Each action from the plan is represented by its own `####` heading.
    -   **Crucially, to ensure the report is a complete, self-contained artifact that prevents context loss between turns, each action log MUST preserve the entire original action block from the plan.** This includes all metadata *and* all content blocks (e.g., the full code block for a `CREATE` action, or both the `FIND` and `REPLACE` blocks for an `EDIT` action). The execution status and details are then appended to this original content.
    -   Every action must have a **Status** (`Approved ✅` or `Skipped 🟡`).
    -   Approved actions must have an **Execution** status (`Success 🟢` or `Failure 🔴`) and may include an `Execution Details` block with outputs or errors.

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
``````
