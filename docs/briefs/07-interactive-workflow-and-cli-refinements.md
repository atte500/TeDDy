# Architectural Brief: Interactive Workflow & CLI Refinements

## 1. Goal (The "Why")

The strategic goal is to evolve `teddy` into a robust, file-based front-end for agentic coding, guided by the "Obsidian for AI coding" philosophy. This involves implementing a seamless, local-first, CLI-driven workflow for stateful, multi-turn AI collaboration.

This brief is based on the canonical specifications that define the new report-centric workflow:
-   [Interactive Session Workflow Specification](/docs/specs/interactive-session-workflow.md)
-   [Report Format Specification](/docs/specs/report-format.md)

## 2. Proposed Solution (The "What")

The solution is centered around a set of new, single-responsibility services orchestrated by a refactored CLI in `main.py`. This modular approach ensures that the complex logic of session management, context generation, and user interaction is decoupled and testable.

1.  **`SessionManager` Service:** A new `SessionManager` service (with an `ISessionManager` port) will encapsulate all filesystem interactions related to sessions (creating directories/files, finding the latest turn, managing session artifacts). This centralizes stateful filesystem logic.

2.  **Report-Centric Workflow:** The core of the solution is a simplified, report-centric workflow orchestrated by the `SessionManager`. The `report.md` from a completed turn serves as the single, complete "worldview" for the AI's next planning phase. This eliminates the need for a complex context-building service and makes the entire process more transparent and robust.

3.  **Refactored CLI & Smart `resume` Command:** The CLI in `main.py` will be refactored to support the new flat command structure (`new`, `resume`, `plan`, etc.). The `resume` command will be the primary entry point for users, intelligently determining whether to initiate a planning or execution phase based on the session's state.

4.  **Two-Tiered Interactive TUI:** The plan approval workflow will be implemented in two tiers:
    -   **Tier 1:** A high-level summary prompt in the `ConsoleInteractorAdapter` will offer `(a)pprove all / (m)odify / (s)kip / (q)uit` options.
    -   **Tier 2:** The `(m)odify` path will launch a full-screen interactive checklist built with the `textual` library, allowing for granular action selection.

5.  **Pre-flight Validation:** To eliminate "approve-then-fail" errors, the `ExecutionOrchestrator` will be updated with a two-phase "dry run" validation process for `CREATE` and `EDIT` actions, calling new preview methods on the `IFileSystemManager` before execution.

6.  **Markdown-First Reporting:** A new `MarkdownReportFormatter` service will be created to convert the `ExecutionReport` domain object into a Markdown string, strictly adhering to the report format spec, including action timings.

## 3. Implementation Analysis (The "How")

This is a large-scale feature that touches multiple layers of the application, from the CLI entry point to the core domain models. The implementation must be broken down into logical, dependency-aware slices to manage complexity.

-   **CLI Refactoring:** The existing `main.py` will be significantly refactored. The current `execute` and `context` commands will be replaced by the new session-aware command suite (`new`, `plan`, `resume`, `branch`, `context`). The old `execute` logic will be preserved for a simplified, session-unaware `execute` command.
-   **New Services:** The new services (`SessionManager`, `MarkdownReportFormatter`) will be created and integrated into the `main.py` composition root.
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
### **Slice 2: Report-Centric Planning Logic**
**Goal:** Implement the core logic for the new report-centric planning phase.

-   **[ ] Task: Update `plan` and `resume` Commands:**
    -   Modify the `plan` and `resume` commands to locate the latest `report.md` in the session.
    -   The full content of this `report.md`, along with the user's new prompt message, will be passed to the `ILlmClient` to generate the next `plan.md`.

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
### **Slice 6: Final Turn Artifacts & User Feedback**
**Goal:** Implement the final turn artifacts and the user feedback loop.

-   **[ ] Task: Update `SessionManager` for New Artifacts:**
    -   Modify the `SessionManager` to create the `system_prompt.xml` file alongside the `plan.md` and `report.md`.
-   **[ ] Task: Update `resume` Command Workflow:**
    -   Implement logic in the `resume` command to prompt for a user message when initiating a new planning phase (i.e., when the latest turn already has a `report.md`).
    -   This user message should be stored in the `User Prompt` field of the *next* turn's `report.md` header.
