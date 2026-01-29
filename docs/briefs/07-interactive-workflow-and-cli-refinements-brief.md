# Architectural Brief: Interactive Workflow & CLI Refinements

## 1. Goal (The "Why")

The strategic goal is to evolve `teddy` into a robust, file-based front-end for agentic coding, guided by the "Obsidian for AI coding" philosophy. This involves implementing a seamless, local-first, CLI-driven workflow while also addressing key reliability, developer experience (DX), and configuration issues from the existing executor.

### Core System Requirements:
-   **New CLI Workflow:** Implement a new flat command structure (`new`, `plan`, `resume`, `branch`, `execute`) to manage the session lifecycle.
-   **Enhanced Interactivity:** Introduce a `(a)pprove all / (m)odify / (s)kip / (q)uit` whole-plan approval prompt and provide unified diffs for complex `EDIT` actions.
-   **Markdown-First Reporting:** The `execute` and `resume` commands must generate a `report.md` in Markdown format.
-   **Specification Alignment:** Align the codebase with the spec (e.g., creating `global.context`).

## 2. Referenced Specifications
-   [Interactive Session Workflow Specification](/docs/specs/interactive-session-workflow.md)
-   [Contextual History & Feedback Loop Specification](/docs/specs/contextual-history-and-feedback.md)
-   [Context Payload Format Specification](/docs/specs/context-payload-format.md)
-   [Core Philosophy](/docs/specs/core-philosophy.md)
-   [Report Format Specification](/docs/specs/report-format.md)

## 3. Proposed Solution (The "What")

The implementation will be centered around a new `SessionManager` service and a refactoring of the CLI commands in `main.py`. The new commands will be top-level, reflecting that the session workflow is the primary mode of interaction.

-   **`SessionManager` Service:** A new service will encapsulate all filesystem interactions related to sessions (creating directories/files, finding the latest turn, checking state).
-   **Smart `resume` Command:** A new `resume` command will act as the primary entry point for continuing a session, intelligently choosing to either execute an existing plan or generate a new one.
-   **Interactive TUI:** For granular control, the `(m)odify` path of the `resume` command will launch a full-screen interactive checklist built with the `textual` library, as validated by a technical spike.
-   **Decoupled `execute` Command:** The `execute` command will be repurposed as a simple, session-unaware utility for running one-off plans from a file or clipboard.

## 4. Implementation Analysis (The "How")

This brief follows the foundational work in the `04-project-restructuring-brief.md` and `05-markdown-parser-brief.md`. It assumes the project structure has been flattened and the Markdown parser is available.

Implementation must be done incrementally through the following dependency-aware vertical slices.

## 5. Vertical Slices

---
### **Slice 1: Session Scaffolding & Core Commands**
**Goal:** Implement the basic file-based session management.

-   **[ ] Task: Implement `SessionManager` Service:**
    -   Define an `ISessionManager` port and a `LocalSessionManagerAdapter`.
    -   Implement the core logic for creating session/turn directories and managing context files.
-   **[ ] Task: Implement Core CLI Commands:**
    -   Refactor `main.py` to support the new flat command structure.
    -   Implement the `new`, `plan`, and `branch` commands, orchestrating calls to the new services.

---
### **Slice 2: Context Payload Generation**
**Goal:** Implement the service responsible for generating the AI's context payload and a new session-aware `context` command.

-   **[ ] Task: Implement `ContextPayloadBuilder` Service:**
    -   Create a new service responsible for generating the complete context payload string.
    -   The service must orchestrate calls to `ISessionManager`, `IFileSystemManager`, and `IRepoTreeGenerator` to gather all required information (system info, tree, memos, file contents).
    -   The output **must** strictly adhere to the format defined in the [Context Payload Format Specification](/docs/specs/context-payload-format.md).
-   **[ ] Task: Implement Session-Aware `context` Command:**
    -   Create a new top-level `context` command.
    -   This command will use the `ContextPayloadBuilder` service to generate the context for the current session and print it to `stdout`.
-   **[ ] Task: Integrate into `plan` and `resume` Commands:**
    -   Update the `plan` and `resume` commands to use the `ContextPayloadBuilder` service to generate the payload that is sent to the LLM.

---
### **Slice 3: Core Workflow & Enhanced Interactivity**
**Goal:** Implement the main `resume` loop and the improved user prompts.

-   **[ ] Task: Implement Smart `resume` Command:**
    -   Implement the logic to check the session state and delegate to either the planning or execution phase.
-   **[ ] Task: Implement `(a)pprove all / (m)odify / (s)kip / (q)uit` Prompt:**
    -   Enhance `ConsoleInteractorAdapter` and `ExecutionOrchestrator` to support the whole-plan approval workflow.
-   **[ ] Task: Implement Tier 2 Interactive TUI:**
    -   Add `textual` as a dependency.
    -   Create the Textual-based interactive checklist for the `(m)odify` option in the `resume` command.
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
**Goal:** Complete the transition to the new Markdown-first workflow, including performance metrics.

-   **[ ] Task: Update Domain Model for Timings:**
    -   In `packages/executor/src/teddy_executor/core/domain/models/execution_report.py`, add a `duration_ms: int | None = None` field to the `ActionLog` dataclass.
-   **[ ] Task: Update `ExecutionOrchestrator` to Capture Timings:**
    -   In `packages/executor/src/teddy_executor/core/services/execution_orchestrator.py`, update the main execution loop to time each action and populate the new `duration_ms` field in the corresponding `ActionLog`.
-   **[ ] Task: Implement Markdown Report Formatter:**
    -   Create a `MarkdownReportFormatter` service to convert the `ExecutionReport` object into a Markdown string.
    -   The output **must** strictly adhere to the format defined in the [Report Format Specification](/docs/specs/report-format.md).
    -   The formatter must render the `start_time`, `end_time`, and action `duration_ms` fields.
    -   Update the `resume` and `execute` commands to use this new formatter.
    -   Ensure the `RESEARCH` action output includes the required hint.

---
### **Slice 7: Contextual History & Enhanced Workflow**
**Goal:** Implement the new turn artifacts and update the session workflow to provide the AI with historical context.

-   **[ ] Task: Update `SessionManager` for New Artifacts:**
    -   Modify the service to create `system_prompt.xml` and `user_prompt.txt` at the start of a planning phase.
-   **[ ] Task: Update `resume` Command Workflow:**
    -   Implement logic in the `resume` command to prompt for a user message when a new planning phase is initiated.
-   **[ ] Task: Implement Automatic Historical Context:**
    -   Update the `ContextPayloadBuilder` to locate the previous turn's `plan.md`, `report.md`, and `user_prompt.txt` and inject them into the `Active Context` for the current turn.

---
### **Slice 8: `READ` Action Refactor & Payload Enhancement**
**Goal:** Implement the new side-effect for the `READ` action and enhance the context payload with token counts and URL support.

-   **[ ] Task: Implement `READ` Action Side-Effect:**
    -   Refactor the `ReadAction` handler and `ExecutionOrchestrator` to implement the system-level side-effect of automatically adding a read file to the next turn's context if it's not already present.
-   **[ ] Task: Update Report for `READ` Action:**
    -   Modify the `MarkdownReportFormatter` to output the new confirmation message for the `READ` action, omitting the full content.
-   **[ ] Task: Enhance `ContextPayloadBuilder`:**
    -   Add support for scraping URLs found in `.context` files.
    -   Implement a token counting mechanism and add the token count to each resource in the `## Resource Contents` section.

---
### **Slice 9: Documentation Alignment**
**Goal:** Update all relevant specifications to reflect the new architecture and workflow defined in the "Contextual History" feature.

-   **[ ] Task: Update `interactive-session-workflow.md`:**
    -   Update the "Core Directory Structure" section with the new turn artifacts (`system_prompt.xml`, `user_prompt.txt`).
    -   Update the `resume` command specification to include the new user prompt behavior.
-   **[ ] Task: Update `context-payload-format.md`:**
    -   Rename `## File Contents` to `## Resource Contents`.
    -   Add `Tokens` and `Resource` metadata fields to the example.
    -   Add an example of a URL resource.
-   **[ ] Task: Update `report-format.md`:**
    -   Update the `READ` action example to show the new, content-free confirmation message.
-   **[ ] Task: Update `new-plan-format.md`:**
    -   Update the `READ` action to clarify its purpose for immediate information gathering, distinct from long-term context management.
