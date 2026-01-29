# Architectural Brief: Interactive Workflow & CLI Refinements

## 1. Goal (The "Why")

The strategic goal is to evolve `teddy` into a robust, file-based front-end for agentic coding, guided by the "Obsidian for AI coding" philosophy. This involves implementing a seamless, local-first, CLI-driven workflow for stateful, multi-turn AI collaboration.

This brief synthesizes the goals from several canonical specifications:
-   [Interactive Session Workflow Specification](/docs/specs/interactive-session-workflow.md)
-   [Contextual History & Feedback Loop Specification](/docs/specs/contextual-history-and-feedback.md)
-   [Context Payload Format Specification](/docs/specs/context-payload-format.md)
-   [Report Format Specification](/docs/specs/report-format.md)

## 2. Proposed Solution (The "What")

The solution is centered around a set of new, single-responsibility services orchestrated by a refactored CLI in `main.py`. This modular approach ensures that the complex logic of session management, context generation, and user interaction is decoupled and testable.

1.  **`SessionManager` Service:** A new `SessionManager` service (with an `ISessionManager` port) will encapsulate all filesystem interactions related to sessions (creating directories/files, finding the latest turn, managing context files). This centralizes stateful filesystem logic.

2.  **`ContextPayloadBuilder` Service:** A dedicated `ContextPayloadBuilder` service will be responsible for generating the complete context payload string sent to the AI. It will orchestrate calls to the `SessionManager` and other services to gather all required information and format it according to the spec, including token counting and historical context.

3.  **Refactored CLI & Smart `resume` Command:** The CLI in `main.py` will be refactored to support the new flat command structure (`new`, `resume`, `plan`, etc.). The `resume` command will be the primary entry point for users, intelligently determining whether to initiate a planning or execution phase based on the session's state.

4.  **Two-Tiered Interactive TUI:** The plan approval workflow will be implemented in two tiers:
    -   **Tier 1:** A high-level summary prompt in the `ConsoleInteractorAdapter` will offer `(a)pprove all / (m)odify / (s)kip / (q)uit` options.
    -   **Tier 2:** The `(m)odify` path will launch a full-screen interactive checklist built with the `textual` library, allowing for granular action selection.

5.  **Pre-flight Validation:** To eliminate "approve-then-fail" errors, the `ExecutionOrchestrator` will be updated with a two-phase "dry run" validation process for `CREATE` and `EDIT` actions, calling new preview methods on the `IFileSystemManager` before execution.

6.  **Markdown-First Reporting:** A new `MarkdownReportFormatter` service will be created to convert the `ExecutionReport` domain object into a Markdown string, strictly adhering to the report format spec, including action timings.

## 3. Implementation Analysis (The "How")

This is a large-scale feature that touches multiple layers of the application, from the CLI entry point to the core domain models. The implementation must be broken down into logical, dependency-aware slices to manage complexity.

-   **CLI Refactoring:** The existing `main.py` will be significantly refactored. The current `execute` and `context` commands will be replaced by the new session-aware command suite (`new`, `plan`, `resume`, `branch`, `context`). The old `execute` logic will be preserved for a simplified, session-unaware `execute` command.
-   **New Services:** The new services (`SessionManager`, `ContextPayloadBuilder`, `MarkdownReportFormatter`) will be created and integrated into the `main.py` composition root.
-   **Core Logic Modifications:** The `ExecutionOrchestrator` is the central hub for many new features. It will be updated to handle action timings, pre-flight validation, and the `READ` action's side-effect.
-   **UI Enhancements:** The `ConsoleInteractorAdapter` will be refactored to support the new two-tiered approval workflow, including the integration of the `textual` library for the interactive checklist.
-   **Port & Model Extensions:** The `IFileSystemManager` port will be extended with new methods for pre-flight validation. The `ActionLog` domain model in `execution_report.py` will be updated to include a `duration_ms` field.

## 4. Vertical Slices

Implementation must be done incrementally through the following dependency-aware vertical slices.

---
### **Slice 1: Session Scaffolding & Core Commands**
**Goal:** Implement the basic file-based session management and the CLI structure.

-   **[ ] Task: Implement `SessionManager` Service:**
    -   Define an `ISessionManager` port and a `LocalSessionManagerAdapter`.
    -   Implement logic for creating session/turn directories and managing context files.
-   **[ ] Task: Refactor CLI in `main.py`:**
    -   Refactor `main.py` to support the new flat command structure.
    -   Implement the `new`, `plan`, and `branch` commands, orchestrating calls to the new `SessionManager`.

---
### **Slice 2: Context Payload Generation**
**Goal:** Implement the service responsible for generating the AI's context payload.

-   **[ ] Task: Implement `ContextPayloadBuilder` Service:**
    -   Create the service to generate the complete context payload string, orchestrating calls to `ISessionManager`, `IFileSystemManager`, and `IRepoTreeGenerator`.
    -   The output must strictly adhere to the [Context Payload Format Specification](/docs/specs/context-payload-format.md), including token counting and URL scraping.
-   **[ ] Task: Implement Session-Aware `context` Command:**
    -   Create the new top-level `context` command that uses the `ContextPayloadBuilder`.
-   **[ ] Task: Integrate into `plan` and `resume` Commands:**
    -   Update `plan` and `resume` to use the `ContextPayloadBuilder` to generate the payload sent to the LLM.

---
### **Slice 3: Core Workflow & Enhanced Interactivity**
**Goal:** Implement the main `resume` loop and the improved user prompts.

-   **[ ] Task: Implement Smart `resume` Command:**
    -   Implement the logic in `main.py` to check session state and delegate to either planning or execution.
-   **[ ] Task: Implement Tier 1 Approval Prompt:**
    -   Refactor `ConsoleInteractorAdapter` to support the `(a)pprove all / (m)odify / (s)kip / (q)uit` prompt.
-   **[ ] Task: Implement Tier 2 Interactive TUI:**
    -   Add `textual` as a dependency.
    -   Create the Textual-based interactive checklist for the `(m)odify` option.

---
### **Slice 4: Action Reliability & Pre-validation**
**Goal:** Eliminate the "approve-then-fail" problem.

-   **[ ] Task: Extend `IFileSystemManager` Port:**
    -   Add `preview_edit()` and `preview_create()` methods to the `IFileSystemManager` port in `file_system_manager.py`.
    -   Implement these methods in the `LocalFileSystemAdapter`.
-   **[ ] Task: Implement "Dry Run" in `ExecutionOrchestrator`:**
    -   Refactor the orchestrator to use a two-phase validation process, calling the new preview methods before execution.

---
### **Slice 5: `READ` Action Refactor & Reporting Enhancements**
**Goal:** Implement the new `READ` side-effect and add timings to the report.

-   **[ ] Task: Update `ActionLog` Domain Model:**
    -   In `execution_report.py`, add `duration_ms: int | None = None` to the `ActionLog` dataclass.
-   **[ ] Task: Update `ExecutionOrchestrator`:**
    -   Update the main execution loop to time each action and populate `duration_ms`.
    -   Implement the system-level side-effect for the `READ` action.
-   **[ ] Task: Implement `MarkdownReportFormatter`:**
    -   Create the `MarkdownReportFormatter` service to convert the `ExecutionReport` object into a Markdown string, adhering to the [Report Format Specification](/docs/specs/report-format.md).
    -   Update the `resume` and `execute` commands to use this new formatter.

---
### **Slice 6: Contextual History & Final Workflow**
**Goal:** Implement the final turn artifacts and AI feedback loop.

-   **[ ] Task: Update `SessionManager` for New Artifacts:**
    -   Modify the service to create `system_prompt.xml` and `user_prompt.txt`.
-   **[ ] Task: Update `resume` Command Workflow:**
    -   Implement logic in the `resume` command to prompt for a user message when initiating a new planning phase.
-   **[ ] Task: Implement Automatic Historical Context:**
    -   Update the `ContextPayloadBuilder` to locate and inject the previous turn's `plan.md`, `report.md`, and `user_prompt.txt` into the context for the new turn.
