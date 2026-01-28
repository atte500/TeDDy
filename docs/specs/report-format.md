# Report Format Specification

## 1. Core Principles

This document specifies the format for `report.md`, the execution report generated after a plan is processed.

1.  **Human & Machine Readable:** The format is Markdown-first, providing a clear, readable summary for humans while maintaining a strict, parsable structure for AI consumption.
2.  **Factual Record:** The report is an immutable, factual log of what occurred during execution. It details which actions were approved, which were skipped, and the precise outcome of each executed action.
3.  **Specular Structure:** The report's structure intentionally mirrors the `plan.md` from which it was generated, providing a clear, side-by-side comparison between what was intended and what was accomplished.

## 2. Overall Document Structure

A report is a single Markdown file with the following top-level structure:

```markdown
# Execution Report: [Original Plan Title]
- **Overall Status:** [Completed | Partial | Failed | Skipped]
- **Original Plan:** [path/to/original/plan.md](/path/to/original/plan.md)
...

## Applied State Changes
... (Optional: Contains reports for Active Context & Memos)

## Action Log
... (Contains a report for each action from the original plan)
```

## 3. Core Component Blocks

### 3.1. Report Header

-   **Purpose:** Contains the report's title and high-level summary metadata.
-   **Format:**
    ```markdown
    # Execution Report: Research and Propose a New "Finisher" Agent Role
    - **Overall Status:** Partial 🟡
    - **Original Plan:** [01/plan.md](/01/plan.md)
    - **Actions:** 5 Total / 4 Approved / 1 Skipped
    - **Outcomes:** 3 Succeeded / 1 Failed
    ```
-   **Parsing Rules:**
    -   The title must start with `Execution Report:`.
    -   The metadata list provides a quick summary of the turn's outcome.

### 3.2. Applied State Changes (Optional)

-   **Purpose:** Confirms which proposed changes to `Active Context` and `Memos` were actually approved and applied.
-   **Format:**
    `````markdown
    ## Applied State Changes

    ### `Active Context`
    - **Status:** Approved
    ````
    [+] docs/briefs/01-finisher-agent-brief.md # Add the new brief to the working set.
    ````

    ### `Memos`
    - **Status:** Skipped
    - **Reason:** User skipped this state change during the interactive review.
    ````
    [+] A new 'Finisher' agent role is being explored.
    [-] The 'Architect' agent is responsible for all handoffs.
    ````
    `````
-   **Parsing Rules:**
    -   This section contains subsections for `Active Context` and `Memos`.
    -   Each subsection must have a **Status** of `Approved` or `Skipped`.
    -   If skipped, the **Reason** must be the verbatim reason provided by the user.
    -   The code block contains the original proposed changes from `plan.md`.

### 3.3. Action Log

-   **Purpose:** Provides a detailed, action-by-action breakdown of the execution. The order of actions must be identical to the original `plan.md`.
-   **Format:** Each action from the plan is represented by its own `###` heading.

#### **Structure for an Executed Action (Approved)**
`````markdown
### `EDIT`
- **Status:** Approved ✅
- **Execution:** Failure 🔴
- **File Path:** [prompts/pathfinder.xml](/prompts/pathfinder.xml)
- **Description:** Temporarily add the Finisher agent to the Pathfinder's list of handoff targets.

#### Execution Details
**Error Output:**
````
Patching failed: The 'FIND' block could not be located in the target file.
...
````
`````

#### **Structure for a Skipped Action**
```markdown
### `INVOKE`
- **Status:** Skipped 🟡
- **Reason:** User chose not to invoke the next agent at this time.
```
-   **Parsing Rules:**
    -   Each action block mirrors the corresponding action in `plan.md`, preserving its heading and metadata (e.g., `File Path`, `Description`).
    -   **Status:** Every action must have a `Status` of `Approved ✅` or `Skipped 🟡`.
    -   **Reason (for Skipped):** If an action is skipped, the `Reason` field must contain the verbatim reason provided by the user.
    -   **Execution (for Approved):** Approved actions must have an `Execution` status of `Success 🟢` or `Failure 🔴`.
    -   **Execution Details (for Approved):** Any output (stdout, stderr, API responses, user replies) must be captured under a `#### Execution Details` heading, followed by a description and a fenced code block.

#### **Special Case: `CHAT_WITH_USER`**
The report for `CHAT_WITH_USER` must capture the user's response.

`````markdown
### `CHAT_WITH_USER`
- **Status:** Approved ✅
- **Execution:** Success 🟢

#### Execution Details
**User Reply:**
````
Yes, this initial direction looks good. Please proceed with the research.
````
`````

## 4. Comprehensive Example Report

`````markdown
# Execution Report: Research and Propose a New "Finisher" Agent Role
- **Overall Status:** Partial 🟡
- **Original Plan:** [01/plan.md](/01/plan.md)
- **Actions:** 5 Total / 4 Approved / 1 Skipped
- **Outcomes:** 3 Succeeded / 1 Failed

## Applied State Changes

### `Active Context`
- **Status:** Approved
````
[+] docs/briefs/01-finisher-agent-brief.md # Add the new brief to the working set.
````

### `Memos`
- **Status:** Approved
````
[+] A new 'Finisher' agent role is being explored.
[-] The 'Architect' agent is responsible for all handoffs.
````

## Action Log

### `RESEARCH`
- **Status:** Approved ✅
- **Execution:** Success 🟢
- **Description:** Research existing software development roles and CI/CD pipeline patterns related to finalization and release management.

#### Execution Details
**Output:**
````json
[
  {"url": "https://example.com/release-manager", "title": "Release Manager Role"},
  {"url": "https://example.com/gitflow", "title": "GitFlow vs Trunk-Based"}
]
````

### `CREATE`
- **Status:** Approved ✅
- **Execution:** Success 🟢
- **File Path:** [docs/briefs/01-finisher-agent-brief.md](/docs/briefs/01-finisher-agent-brief.md)
- **Description:** Create the initial draft of the brief for the new "Finisher" agent.

### `EDIT`
- **Status:** Approved ✅
- **Execution:** Failure 🔴
- **File Path:** [prompts/pathfinder.xml](/prompts/pathfinder.xml)
- **Description:** Temporarily add the Finisher agent to the Pathfinder's list of handoff targets.

#### Execution Details
**Error:**
````
Patch failed: FIND block could not be located in prompts/pathfinder.xml.
````

### `CHAT_WITH_USER`
- **Status:** Approved ✅
- **Execution:** Success 🟢

#### Execution Details
**User Reply:**
````
Yes, this initial direction looks good. Please proceed with the research.
````

### `INVOKE`
- **Status:** Skipped 🟡
- **Reason:** I want to fix the failing EDIT action before handing off to the next agent.
- **Agent:** Architect
`````
