# Architectural Brief: Interactive Workflow & CLI Refinements

## 1. Goal (The "Why")

The strategic goal is to evolve `teddy` into a robust, file-based front-end for agentic coding, guided by the "Obsidian for AI coding" philosophy. This involves implementing a seamless, local-first, CLI-driven workflow for stateful, multi-turn AI collaboration.

This brief is based on the canonical specifications that define the new context-centric workflow:
-   [Interactive Session Workflow Specification](/docs/specs/interactive-session-workflow.md)
-   [Context Payload Format Specification](/docs/specs/context-payload-format.md)
-   [Report Format Specification](/docs/specs/report-format.md)

## 2. Proposed Solution (The "What")

The solution is centered around a set of new, single-responsibility services orchestrated by a refactored CLI in `main.py`. This modular approach ensures that the complex logic of session management, context generation, and user interaction is decoupled and testable.

1.  **`SessionManager` Service:** A new `SessionManager` service (with an `ISessionManager` port) will encapsulate all filesystem interactions related to sessions (creating directories/files, finding the latest turn, managing session artifacts). This centralizes stateful filesystem logic.

2.  **Context-Centric Workflow:** The core of the solution is a context-centric workflow where a dedicated `input.md` file serves as the AI's complete worldview. This payload is generated implicitly by the `plan` and `resume` commands, ensuring the AI always has the most up-to-date context. This decouples the historical `report.md` from the forward-looking planning process.

3.  **Refactored CLI & Smart `resume` Command:** The CLI in `main.py` will be refactored to support the new command structure (`new`, `resume`, `plan`, `execute`, and an optional `context`). The `resume` command will be the primary entry point for users, intelligently determining whether to initiate a planning or execution phase based on the session's state.

4.  **Two-Tiered Interactive TUI:** The plan approval workflow will be implemented in two tiers:
    -   **Tier 1:** A high-level summary prompt in the `ConsoleInteractorAdapter` will offer `(a)pprove all / (m)odify / (s)kip / (q)uit` options.
    -   **Tier 2:** The `(m)odify` path will launch a full-screen interactive checklist built with the `textual` library, allowing for granular action selection.

5.  **Pre-flight Validation:** To eliminate "approve-then-fail" errors, the `ExecutionOrchestrator` will be updated with a two-phase "dry run" validation process for `CREATE` and `EDIT` actions, calling new preview methods on the `IFileSystemManager` before execution.

6.  **Markdown-First Reporting:** A new `MarkdownReportFormatter` service will be created to convert the `ExecutionReport` domain object into a Markdown string, strictly adhering to the report format spec, including action timings.

## 3. Implementation Analysis (The "How")

This is a large-scale feature that touches multiple layers of the application, from the CLI entry point to the core domain models. The implementation must be broken down into logical, dependency-aware slices to manage complexity.

-   **CLI Refactoring:** The `main.py` file will be significantly refactored to support the new session-aware command suite (`new`, `plan`, `resume`, `execute`, and `context`). The `context` logic will be implemented as a core service implicitly called by `plan` and `resume`, and optionally exposed as a standalone command for debugging.
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
    -   Implement logic for creating session/turn directories according to the [TeDDy Directory Structure Specification](/docs/specs/teddy-directory-structure.md).
-   **[ ] Task: Refactor CLI in `main.py`:**
    -   Refactor `main.py` to support the new command structure.
    -   Implement the `new`, `plan`, `execute` commands.

---
### **Slice 2: Context-Centric Workflow**
**Goal:** Implement the core logic for generating the `input.md` payload and using it for planning.

-   **[ ] Task: Implement Context Service:**
    -   Create a `ContextService` responsible for the logic of gathering context files and building the `input.md` payload, adhering to the [Context Payload Format Specification](/docs/specs/context-payload-format.md).
-   **[ ] Task: Integrate Context Service into CLI:**
    -   Modify the `plan` command to call the `ContextService` to generate `input.md` before calling the `ILlmClient`.
    -   Expose the `ContextService` logic via a standalone `teddy context` command for debugging.
    -   The `ILlmClient` will now consume the content of `input.md` as its primary input.

---
### **Slice 3: Core Workflow & Enhanced Interactivity**
**Goal:** Implement the main `resume` loop and the improved user prompts.

-   **[ ] Task: Implement Smart `resume` Command:**
    -   Implement the logic in `main.py` to check session state and delegate to either planning (which now includes implicit context generation) or execution.
-   **[ ] Task: Implement Tier 1 Approval Prompt:**
    -   Refactor `ConsoleInteractorAdapter` to support the `(a)pprove all / (m)odify / (s)kip / (q)uit` prompt.
-   **[ ] Task: Implement Tier 2 Interactive TUI:**
    -   Add `textual` as a dependency.
    -   Create the Textual-based interactive checklist for the `(m)odify` option.

---
### **Slice 4: Action Reliability & Pre-validation**
**Goal:** Eliminate the "approve-then-fail" problem.

-   **[ ] Task: Extend `IFileSystemManager` Port:**
    -   Add `preview_edit()` and `preview_create()` methods to the `IFileSystemManager` port.
-   **[ ] Task: Implement "Dry Run" in `ExecutionOrchestrator`:**
    -   Refactor the orchestrator to use a two-phase validation process, calling the new preview methods before execution.

---
### **Slice 5: Action Side-Effects & Reporting**
**Goal:** Implement the forward-looking side-effects for context-modifying actions and the simplified reporting.

-   **[ ] Task: Update `ActionLog` Domain Model:**
    -   In `execution_report.py`, add `duration_ms: int | None = None` to the `ActionLog` dataclass.
-   **[ ] Task: Update `ExecutionOrchestrator`:**
    -   Update the main execution loop to time each action and populate `duration_ms`.
    -   Implement the system-level side-effects for `READ`, `PRUNE`, and `INVOKE` actions, ensuring they modify the artifacts in the *next* (`N+1`) turn directory.
    -   Ensure the path of a report just generated (e.g., `01/report.md`) is added to the `02/turn.context` file.
-   **[ ] Task: Implement `MarkdownReportFormatter`:**
    -   Create the `MarkdownReportFormatter` service to convert the `ExecutionReport` object into a simplified Markdown string, adhering to the updated [Report Format Specification](/docs/specs/report-format.md).
