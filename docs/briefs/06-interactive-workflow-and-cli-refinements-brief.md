# Architectural Brief: Interactive Workflow & CLI Refinements

## 1. Goal (The "Why")

The strategic goal is to evolve `teddy` into a robust, file-based front-end for agentic coding, guided by the "Obsidian for AI coding" philosophy. This involves implementing a seamless, local-first, CLI-driven workflow while also addressing key reliability, developer experience (DX), and configuration issues from the existing executor.

### Core System Requirements:
-   **New CLI Workflow:** Implement a new flat command structure (`new`, `plan`, `resume`, `branch`, `execute`) to manage the session lifecycle.
-   **Enhanced Interactivity:** Introduce a `y/n/yolo` whole-plan approval prompt and provide unified diffs for complex `EDIT` actions.
-   **Markdown-First Reporting:** The `execute` and `resume` commands must generate a `report.md` in Markdown format.
-   **Specification Alignment:** Align the codebase with the spec (e.g., creating `global.context`).

## 2. Architectural Approach (The "What")

The implementation will be centered around a new `SessionManager` service and a refactoring of the CLI commands in `main.py`. The new commands will be top-level, reflecting that the session workflow is the primary mode of interaction.

-   **`SessionManager` Service:** A new service will encapsulate all filesystem interactions related to sessions (creating directories/files, finding the latest turn, checking state).
-   **Smart `resume` Command:** A new `resume` command will act as the primary entry point for continuing a session, intelligently choosing to either execute an existing plan or generate a new one.
-   **Decoupled `execute` Command:** The `execute` command will be repurposed as a simple, session-unaware utility for running one-off plans from a file or clipboard.

## 3. Key Architectural Considerations & Slices (The "How")

This is a large-scale initiative that consolidates the legacy `05-cli-refinements` and `06-interactive-session-workflow` briefs into a single, cohesive plan. Implementation must be done incrementally through the following dependency-aware vertical slices.

---
### **Slice 1: Project Restructuring & Foundational Services**
**Goal:** Prepare the codebase for the new workflow and establish core services.

-   **[ ] Task: Restructure Repository:**
    -   Move all contents of `packages/executor/` to the project root.
    -   Delete the obsolete `packages/tui/` directory.
    -   Update all imports, `pyproject.toml`, and CI scripts to reflect the new structure.
-   **[ ] Task: Implement `ConfigService`:**
    -   Create a service to read settings from `.teddy/config.yaml` as the primary source, falling back to environment variables. This will manage settings like `TEDDY_DIFF_TOOL` and `open_after_action`.
-   **[ ] Task: Implement `ILlmClient` Port:**
    -   Add `litellm` as a dependency.
    -   Define an `ILlmClient` outbound port.
    -   Create a `LiteLLMAdapter` that implements the port.
    -   Wire up the adapter in the `main.py` composition root.

---
### **Slice 2: Session Scaffolding & Core Commands**
**Goal:** Implement the basic file-based session management.

-   **[ ] Task: Implement `SessionManager` Service:**
    -   Define an `ISessionManager` port and a `LocalSessionManagerAdapter`.
    -   Implement the core logic for creating session/turn directories and managing context files.
-   **[ ] Task: Implement Core CLI Commands:**
    -   Refactor `main.py` to support the new flat command structure.
    -   Implement the `new`, `plan`, and `branch` commands, orchestrating calls to the new services.

---
### **Slice 3: Core Workflow & Enhanced Interactivity**
**Goal:** Implement the main `resume` loop and the improved user prompts.

-   **[ ] Task: Implement Smart `resume` Command:**
    -   Implement the logic to check the session state and delegate to either the planning or execution phase.
-   **[ ] Task: Implement `y/n/yolo` Prompt:**
    -   Enhance `ConsoleInteractorAdapter` and `ExecutionOrchestrator` to support the whole-plan approval workflow.
-   **[ ] Task: Implement Simplified Approval Prompts:**
    -   Update the prompt-building logic to show a cleaner, summarized view of each action.

---
### **Slice 4: Action Reliability & Pre-validation**
**Goal:** Eliminate the "approve-then-fail" problem by implementing a pre-flight check.

-   **[ ] Task: Implement "Dry Run" Pre-validation:**
    -   Refactor `ExecutionOrchestrator` to use a two-phase validation process for file actions (`create`, `edit`).
    -   Add `preview_edit()` and `preview_create()` methods to the `IFileSystemManager` port and `LocalFileSystemAdapter`.
    -   Enrich custom file system exceptions to include file content at the moment of failure.

---
### **Slice 5: DX Enhancements & Bug Fixes**
**Goal:** Improve the developer experience and fix legacy bugs.

-   **[ ] Task: Implement File-Based Previews:**
    -   Refactor `ConsoleInteractorAdapter` to use temporary files for previewing `CREATE` and `CHAT_WITH_USER` actions in an external editor.
-   **[ ] Task: Implement UI Polish:**
    -   Add color-coded terminal diffs and a one-time hint for configuring an external diff tool.
-   **[ ] Task: Implement `open_after_action`:**
    -   Add logic to `ExecutionOrchestrator` to automatically open created/edited files in an editor, based on the new config flag.
-   **[ ] Task: Fix `read` action for URLs:**
    -   Update the `ReadAction` handler to accept `IWebScraper` and delegate to it when the path is a URL.
-   **[ ] Task: Add `description` to Report:**
    -   Add the optional `description` field to the `ActionLog` model and ensure it's populated by the `ActionDispatcher`.

---
### **Slice 6: Markdown Reporting & Finalization**
**Goal:** Complete the transition to the new Markdown-first workflow.

-   **[ ] Task: Implement Markdown Report Formatter:**
    -   Create a `MarkdownReportFormatter` service to convert the `ExecutionReport` object into a Markdown string.
    -   Update the `resume` and `execute` commands to use this new formatter.
    -   Ensure the `RESEARCH` action output includes the required hint.
-   **[ ] Task: Deprecate Legacy Logic:**
    -   The old YAML parsing logic for bug fixes (e.g., handling colons) can now be deprecated in favor of the new Markdown parser.
