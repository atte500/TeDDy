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

4.  **Context-Aware Interactive TUI:** The plan approval workflow will be implemented using a sophisticated, multi-layered TUI that allows for rich interaction, including manual editing of the plan.
    -   **Tier 1 (Approval Prompt):** The initial prompt will now include an option to review the full plan (`(r)eview full plan`) before deciding on a course of action.
    -   **Tier 2 (Interactive Checklist):** The `(m)odify` option will launch a `textual`-based checklist. This is no longer a simple selection tool; it is the entry point for the **"Context-Aware Editing"** model. Pressing `(p)` on a highlighted action will trigger a preview/edit workflow that is specific to the action type (`CREATE`, `EDIT`, `EXECUTE`, etc.), including non-blocking calls to external editors.
    -   **Audit Trail:** All user modifications will be tracked and explicitly noted in the final `report.md` to ensure a complete and accurate audit trail.

5.  **Plan Validation & Automated Re-planning:** Before any plan is presented to the user, it will undergo a comprehensive validation phase. This checks for common errors like `FIND` block mismatches, `CREATE` conflicts, and context violations. If validation fails, an automated re-planning loop is triggered, instructing the AI to correct its own plan based on the specific validation errors. This entire process is detailed in the canonical [Interactive Session Workflow Specification](/docs/specs/interactive-session-workflow.md).

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
**Goal:** Implement the main `resume` loop and the new "Context-Aware Editing" TUI.

-   **[ ] Task: Implement Smart `resume` Command:**
    -   Implement the logic in `main.py` to check session state and delegate to either planning (which now includes implicit context generation) or execution.
-   **[ ] Task: Implement Tier 1 Approval Prompt:**
    -   Refactor `ConsoleInteractorAdapter` to support the `(a)pprove all / (r)eview full plan / (m)odify / (s)kip / (q)uit` prompt.
-   **[ ] Task: Implement Core `textual` TUI Framework:**
    -   Add `textual` as a dependency.
    -   Create the base interactive checklist, including navigation, selection, and the `(p)` keybinding for preview/edit.
-   **[ ] Task: Implement In-Terminal Editor for Simple Actions:**
    -   For actions like `EXECUTE`, `RESEARCH`, etc., implement the in-terminal preview and edit prompt.
-   **[ ] Task: Implement Non-Blocking Editor for `CREATE`:**
    -   Implement the "Save As" workflow: launch a non-blocking editor for content, and simultaneously prompt for the file path in the terminal.
    -   Implement the final user confirmation step to synchronize the action.
-   **[ ] Task: Implement Non-Blocking Editor for `EDIT`:**
    -   Implement the workflow: create a temporary file with the proposed changes, launch a non-blocking editor, and use a final confirmation prompt for synchronization.
-   **[ ] Task: Implement Modification Tracking:**
    -   Add logic to detect if a user has actually changed an action.
    -   Apply a `*modified` tag in the UI only when changes have been made.
    -   Update the `report.md` generation to include a "modified by user" indicator for any edited actions.

---
### **Slice 4: Plan Validation & Automated Re-planning**
**Goal:** Eliminate "approve-then-fail" errors by implementing a robust pre-flight validation and self-correction loop.

-   **[ ] Task: Implement Plan Validator Service:**
    -   Create a new `PlanValidator` service responsible for executing all pre-flight checks as defined in the specification (e.g., `FIND` block matching, `CREATE` conflicts, `EDIT`/`PRUNE` context requirements).
-   **[ ] Task: Integrate Validator into `execute` Command:**
    -   In `main.py`, before the approval phase of the `execute` command, invoke the `PlanValidator`.
-   **[ ] Task: Implement Automated Re-plan Loop:**
    -   If validation fails, implement the logic to:
        1.  Generate a failure report.
        2.  Prepare the feedback payload (errors + faulty plan).
        3.  Initiate the next turn without adding the failure report to the context.
        4.  Automatically call the `plan` command with the feedback payload.
        5.  Terminate the current execution.

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

---
### **Slice 6: Agent Collaboration Model**
**Goal:** Evolve the session workflow to support branching and specialist agent sub-routines.

-   **[ ] Task: Implement `meta.yaml` Ledger:**
    -   Update the `SessionManager` to create and manage the `meta.yaml` file in each turn directory.
    -   Ensure it correctly populates `turn_id`, `parent_turn_id`, and `caller_turn_id` based on the turn transition logic.
-   **[ ] Task: Enhance Plan Parser:**
    -   Add support for the `CONCLUDE` action.
    -   Update `INVOKE` and add `CONCLUDE` to parse the optional `Handoff Resources` list.
-   **[ ] Task: Refactor `ExecutionOrchestrator` for Branching:**
    -   Refactor the orchestrator (or a higher-level service) to fully implement the "Turn Transition Algorithm" from the `interactive-session-workflow.md` spec. This is the core of this slice.
-   **[ ] Task: Create Acceptance Tests:**
    -   Develop end-to-end tests for the `INVOKE`/`CONCLUDE` cycle.
    -   Include a test for a multi-turn specialist agent to validate that `caller_turn_id` is correctly managed.
-   **[ ] Task: Update Agent Prompts:**
    -   Review and update all agent prompts (`prompts/*.xml`) to utilize the new `CONCLUDE` action and the `Handoff Resources` format for `INVOKE`.
