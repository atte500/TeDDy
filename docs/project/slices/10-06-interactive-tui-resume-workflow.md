# Slice 09-06: Interactive TUI & resume Workflow
- **Status:** [✓] Completed

## 1. Business Goal
To provide a professional, interactive experience for reviewing and modifying AI plans before execution. This includes the "smart resume" capability to intelligently pick up where a session left off, a "Streamlined Initialization" flow where new sessions immediately trigger planning, and a Textual-based TUI for granular control over action execution and modification.

- **Source Milestone:** [Milestone 09: Interactive Session Workflow & LLM Integration](/docs/project/milestones/10-interactive-session-and-config.md)

## 2. Preliminary Refactoring
- **Unfreeze Plan Domain:** The `Plan` and `ActionData` dataclasses in `src/teddy_executor/core/domain/models/plan.py` must be unfrozen (`frozen=False`) to allow the TUI to modify them during the "Modify & Preview" phase, or a `replace()` based transformation pattern must be established.
- **Session State Logic:** Move the state detection logic from `session_cli_handlers.py` into the `SessionService` to make it reusable and testable.

## 3. Interaction Sequence

### The 'resume' Orchestration
1. **Trigger:** User runs `teddy resume` from within a session or turn directory, or creates a new session with `teddy new`.
2. **Detection:** `SessionService` identifies the latest turn and its state:
   - **Case A: Empty Turn** (No `plan.md`) -> Trigger `teddy plan` (Context -> LLM).
   - **Case B: Pending Plan** (`plan.md` exists, no `report.md`) -> Trigger `teddy execute`.
   - **Case C: Complete Turn** (`report.md` exists) -> Prompt user for input, then start Turn N+1.
3. **Execution:** The command invokes the appropriate service based on the state.

### The TUI Approval Flow (Tier 1 & 2)
1. **Trigger:** `teddy execute` is called in interactive mode.
2. **Tier 1 (Summary):** A high-level view of actions is shown.
3. **Tier 2 (Checklist):** If user selects `(m)odify`, the Textual TUI opens:
   - Displays a tree/list of all actions with checkboxes.
   - **Preview (p):** Opens the "Context-Aware Editing" view.
   - **Modify:** Allows changing file paths for `CREATE` or editing `FIND/REPLACE` blocks for `EDIT`.
   - **Submit (s):** Executes only the checked/modified actions.

## 4. Acceptance Criteria (Scenarios)

### Scenario: Resume picks up pending execution [✓]
- **Given** a turn directory with `plan.md` but no `report.md`.
- **When** I run `teddy resume`.
- **Then** it MUST automatically start the execution/approval flow for that plan.

### Scenario: Resume starts new turn after completion [✓]
- **Given** a turn directory with a completed `report.md`.
- **When** I run `teddy resume`.
- **Then** it MUST prompt me for instructions and trigger a new planning phase for the next turn.

### Scenario: TUI allows partial execution [✓]
- **Given** a plan with 3 actions.
- **When** I run `teddy execute` and enter the TUI (Modify mode).
- **And** I uncheck the 2nd action and press `(s)` to submit.
- **Then** only the 1st and 3rd actions MUST be executed.
- **And** the `report.md` MUST mark the 2nd action as `SKIPPED` by user.

**Implementation Notes:**
- Established `IPlanReviewer` inbound port for interactive review.
- Updated `ActionData` domain model with `selected` boolean field (defaults to `True`).
- Refactored `ExecutionOrchestrator` to inject `IPlanReviewer` and call it during `execute()`.
- Implemented action skipping logic in `ExecutionOrchestrator` for unselected actions.
- Added `tests/acceptance/test_partial_execution.py` to verify the flow with a `FakeReviewer`.

### Scenario: Context-Aware Editing of CREATE action [✓]
- **Given** a `CREATE` action for `src/foo.py`.
- **When** I press `(p)` in the TUI.
- **And** I change the path to `src/bar.py` and modify the content in the external editor.
- **Then** the final execution MUST create `src/bar.py` with the modified content.

**Implementation Notes:**
- Implemented `_preview_create` in `ReviewerApp` using `with self.suspend():` to yield terminal control to external editors.
- Added `modified` boolean to `ActionData` model to track user overrides.
- Verified that labels in the TUI are updated with a `*modified` tag after editing.

### Scenario: Context-Aware Editing of EDIT action [✓]
- **Given** an `EDIT` action with a series of FIND/REPLACE blocks.
- **When** I press `(p)` in the TUI.
- **Then** the tool MUST present the *proposed* final content in the editor (original content + AI edits).
- **And** if I modify that content, the action MUST be converted to a content-override in the final plan.

**Implementation Notes:**
- Implemented `_preview_edit` in `ReviewerApp`.
- Integrated `EditSimulator.simulate_edits` to generate the "proposed state" for the editor.
- Verified that manual user changes bypass the original AI edits and are applied as a direct content override during execution.

### Scenario: Textual TUI Backbone & Checklist [✓]
- **Given** a plan with multiple actions.
- **When** the TUI opens.
- **Then** it MUST show a hierarchical tree of actions with their current selection state.

**Implementation Notes:**
- Developed `ReviewerApp` inheriting from `textual.app.App`.
- Implemented `on_tree_node_selected` to toggle selection with the `enter` key.
- Implemented `Toggle All` (`a`) using unselect-all/select-all logic.
- Standardized the naming convention of `FileSystemManager` to `IFileSystemManager` globally across `src/` and `tests/` to align with the `I-prefix` standard for ports.

## 5. User Showcase
1. **Streamlined Initialization:** Run `teddy new tui-test`.
   - **Verify:** The system should automatically initialize the session AND trigger the first planning phase, prompting you for your initial instructions.
2. **Interactive Modification:** Once the plan is generated, the system should present the High-Level Summary (Tier 1).
3. Select `(m)odify` to enter the TUI (Tier 2).
4. **Action Selection:** Uncheck one action using the TUI interface.
5. **Context-Aware Editing:** Highlight another action and press `(p)` to preview/edit its content or target path.
6. **Execution:** Press `(s)` to submit the modified plan.
7. **Verification:** Check the generated `report.md` in turn `01/` and the `session-log.md` to verify that the skipped and modified actions are correctly recorded.

## 6. Architectural Changes

### Core Logic
- **`IPlanReviewer` ([Contract](/docs/architecture/core/ports/inbound/plan_reviewer.md))**: New inbound port for interactive plan review.
- **`Plan` Domain Model**: Unfrozen to allow in-memory modification.
- **`SessionService`**: Updated to include state detection logic (`get_session_state`) for the `resume` command.
- **`SessionOrchestrator`**: New `resume()` method implementing the state machine.

### Adapters
- **`TextualPlanReviewer` ([Design](/docs/architecture/adapters/inbound/textual_plan_reviewer.md))**: New primary adapter implementing the Textual TUI.
- **`CLI Adapter`**: Updated to support `resume` and streamlined `new`.

## 7. Deliverables

### 1. Dependencies & Foundation
- [✓] **TUI Dependencies:** Add `textual` to `pyproject.toml`.
- [✓] **Model Refactoring:** Unfreeze `Plan` and `ActionData`.

### 2. Session Intelligence
- [✓] **Session State Engine:** Implement `SessionService.get_session_state()`.
- [✓] **Resume Orchestrator:** Implement `SessionOrchestrator.resume()`.
- [✓] **Streamlined CLI:** Implement `teddy resume` and streamlined `teddy new`.

### 3. Interactive TUI (The Reviewer)
- [✓] **Textual Backbone:** Implement the basic `ReviewerApp` with Tier 1/2 views.
- [✓] **Action Checklist:** Implement selection logic for partial execution.
- [✓] **Context-Aware Editing:** Implement the `(p)` preview/modify workflow for `CREATE` and `EDIT` actions.

### 4. Verification
- [✓] **Unit Tests:** `ReviewerApp` interaction and logic (9 passing).
- [✓] **Integration Tests:** `SessionOrchestrator` validation and transition logic.
- [✓] **Acceptance Tests:** `test_interactive_execution.py`, `test_partial_execution.py`, `test_context_aware_editing.py`.
- [✓] **Global Stability:** All 337 tests passing after naming standardization.
