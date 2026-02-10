# Specification: Manual CLI Workflow

## 1. Overview

This document specifies the user experience and system behavior for a non-interactive, manual workflow using the `teddy` CLI with an external chat interface. The goal is to provide a smooth, copy-paste-driven experience that remains robust and informative, even without the stateful, interactive session manager.

## 2. Guiding Principles

-   **Clipboard-First:** The primary method for passing multi-line text (plans, reports, context) between the user and the tool is the system clipboard.
-   **Stateless & Explicit:** Each `teddy execute` command is a self-contained operation. The execution report must contain all necessary information for the user and AI to decide on the next step.
-   **User-in-the-Loop:** The user is responsible for bridging the gap between the `teddy` tool and the AI. The tool's output must be designed to make this as seamless as possible.
-   **Robust Markdown Generation (Smart Fencing):** All system-generated Markdown containing file contents (e.g., in reports from `teddy execute` or context payloads from `teddy context`) must use dynamic code fencing. The number of backticks used for a code block's fence must be greater than the longest sequence of backticks found within the content itself, preventing parsing errors.

## 3. The Core Workflow Loop

The standard "happy path" for the manual workflow is a cycle of context gathering, planning, and execution.

1.  **`teddy context`:** The user runs `teddy context`. The command gathers all relevant project information and **copies it to the clipboard**.
2.  **User Pastes to AI:** The user pastes the context payload from their clipboard into the external chat UI, along with their prompt for the AI.
3.  **AI Generates Plan:** The AI returns a plan in valid Markdown format. The user **copies the entire Markdown plan to the clipboard**.
4.  **`teddy execute`:** The user runs `teddy execute`.
    -   By default, the command reads the plan from the clipboard.
    -   It then enters the **Action-by-Action Approval Loop** (see section 3.1).
    -   After the loop is complete, it generates and outputs a **Concise Report** (see section 4).
    -   It **copies the final Markdown report to the clipboard** (this can be disabled with a `--no-copy` flag).
5.  **User Pastes Report to AI:** The user pastes the concise report from their clipboard back to the AI, starting the next cycle.

### 3.1. The Action-by-Action Approval Loop
A core safety feature of TeDDy is the approval loop. When `teddy execute` is run without the `-y` flag, it iterates through each action and initiates an interactive approval process:

1.  **Display Action Details:** The tool first prints a clear summary of the action to be performed, including its type, description, and parameters.
2.  **Provide a Visual Diff (for file changes):**
    -   For `create_file` and `edit` actions, the tool automatically generates a visual diff.
    -   It will attempt to open a dedicated diff view in an external tool if one is configured (`TEDDY_DIFF_TOOL` environment variable) or if VS Code (`code` command) is found.
    -   If no external tool is available, it will fall back to printing a colorized diff directly in the terminal.
3.  **Prompt for Confirmation:** After presenting the details (and diff, if applicable), the tool will display a final confirmation prompt: `Approve? (y/n):`.
4.  **Handle User Decision:**
    -   If the user enters `y` (or `yes`), the action is executed.
    -   If the user enters `n` (or `no`), the action is skipped, and they are prompted for an optional `Reason for skipping:`.

## 4. `teddy execute` CLI Output

### 4.1. Report Generation: The Concise Report

The manual workflow uses a **Concise Report** for its CLI output, which is optimized for a chat-based, copy-paste workflow. This report is a compact rendering of the canonical report data model.

The canonical data model and the distinction between the "Rich Report" (for files) and the "Concise Report" (for CLI) are formally defined in the [Report Format Specification](./report-format.md).

The primary characteristics of the Concise Report are:
-   It includes a top-level execution summary (`Overall Status`, timings, etc.).
-   It includes special, context-aware sections (Failures, `READ` additions, etc.), as needed.
-   Its Action Log includes all action metadata and status but **omits** the large, verbatim content blocks from the original plan (e.g., the `Rationale` and the full bodies of `CREATE` or `EDIT` actions).

## 5. Special Sections in the Concise Report

The concise report will conditionally include the following sections as needed.

### 5.1. Handling `READ` Action Side-Effects

When a `READ` action is successfully executed, the system's internal logic would normally add the file to the next turn's context. In the manual workflow, this must be made explicit.

-   **Requirement:** If any `READ` actions were successful, the report must include a top-level `## Resource Contents` section. This section provides the full, verbatim content of the read files.

-   **Example Report Snippet:**
    `````markdown
    # Execution Report: ...
    - **Overall Status:** Completed 🟢
    ...

    ## Resource Contents
    The following resource contents were successfully read.
    ---
    **Resource:** `[docs/ARCHITECTURE.md](/docs/ARCHITECTURE.md)`
    ````markdown
    # System Architecture: TeDDy
    ... (full content of the architecture file) ...
    ````
    ---

    ## Execution Summary
    ...
    `````

### 5.2. Handling Failures
When an action fails, the report must provide a complete, self-contained "error report" that the user can paste directly to the AI for self-correction.

-   **Requirement:** If any action fails, the report must include a top-level `## Failed Action Details` section.
-   This section will contain the detailed error message for each failed action.
-   **Special Case for `CREATE`/`EDIT`:** If a `CREATE` or `EDIT` action fails, the system must include the *actual, current content* of the target file(s) in this section. To avoid redundancy, a file's content will only be included **once**, even if multiple actions failed on the same file.

-   **Example Report Snippet:**
    `````markdown
    # Execution Report: ...
    - **Overall Status:** Failed 🔴
    ...

    ## Failed Action Details

    ### `EDIT` on `pyproject.toml`
    - **Error:** `FIND` block did not match the file's content.

    ### `CREATE` on `src/new.py`
    - **Error:** File already exists.

    ### Resource Contents
    ---
    **Resource:** `[pyproject.toml](/pyproject.toml)`
    ````toml
    [tool.poetry]
    name = "teddy_executor"
    ... (actual, current content of the file) ...
    ````
    ---
    **Resource:** `[src/new.py](/src/new.py)`
    ````python
    # some pre-existing content
    ````
    ---

    ## Execution Summary
    ...
    `````

### 5.3. Handling Unsupported Actions (`INVOKE`, `CONCLUDE`, `MEMO`)
The `INVOKE`, `CONCLUDE`, and `MEMO` actions are specific to stateful, automated workflows and have no equivalent in the manual mode.

-   **Requirement:** If a plan contains an `INVOKE`, `CONCLUDE`, or `MEMO` action, the executor should treat it as a no-op. The action will be logged in the report with a status indicating it was recognized but skipped because it is unsupported in this mode.

-   **Example Report Snippet:**
    ````markdown
    #### `INVOKE`
    - **Status:** Skipped 🟡
    - **Execution:** Not Supported
    - **Agent:** Architect
    - **Details:** This action is not supported in non-interactive/manual execution mode.
    ````

## 6. Pre-flight Validation
To ensure robustness and provide fast feedback, a comprehensive validation phase must be executed *before* any action is performed, regardless of the workflow mode (interactive or manual).

-   **Requirement:** Before attempting execution, the `teddy execute` command MUST run a series of pre-flight checks against the plan and the current workspace. The complete, canonical list of these checks is defined in the **[Plan Validation Specification](/docs/specs/plan-format-validation.md)**.

-   **Behavior in Manual Workflow:** If any validation check fails:
    1.  Execution is **immediately terminated**. No actions are performed.
    2.  A special Markdown report is generated, printed to `stdout`, and copied to the clipboard.
    3.  This report will have an `Overall Status: Validation Failed 🔴` and will contain a `## Validation Errors` section detailing each specific failure. This provides the user with a clear, actionable error message to provide to the AI for correction.
