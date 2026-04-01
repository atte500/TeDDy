# Slice 00-04: TUI UX Polish and Refinements
- **Status:** Planned
- **Milestone:** [Milestone 10: Interactive Session Workflow & LLM Integration](/docs/project/milestones/10-interactive-session-and-config.md)
- **Reference Prototype:** [prototypes/tui_canonical_final.py](/prototypes/tui_canonical_final.py)

## 1. Business Goal
To refine the plan review TUI by implementing a more robust interaction model based on user feedback. The goal is to provide clear visual feedback for action status (pending, modified, executed) and a streamlined editing workflow that uses the user's external editor.

## 2. Scenarios

### Scenario: Informative Header Display
> As a user, I want the header to show the plan's title and status, so I always have context for what I'm reviewing.

- **Given** a plan is loaded into the `ReviewerApp`.
- **When** the TUI is rendered.
- **Then** the `Header` widget MUST display the plan's title and status emoji in the center.
- **And** the `Header` widget MUST display a clock on the right.

#### Deliverables
- [✓] **Logic** - In `ReviewerApp.on_mount`, dynamically set `self.title` from `self.plan.title` and `self.plan.metadata["Status"]` (extracting the status emoji).
- [✓] **Wiring** - In `ReviewerApp.compose`, the Header widget must be configured with show_clock=True.

### Scenario: Dual-Pane Layout with Comprehensive Parameter Inspection
> As a user, I want to see all available parameters for an action, including defaults, so I understand the full range of options.

- **Given** an action is highlighted in the `ActionTree`.
- **When** the `ParameterList` panel on the right is populated.
- **Then** it MUST display all possible parameters for that action type, showing the actual value if present, or the system's default value if not.

#### Deliverables
- [✓] **Layout** - Refactor `ReviewerApp.compose` to use a `Horizontal` layout containing the `ActionTree` and a new `ParameterList` widget.
- [✓] **Widget** - Create a new `ParameterList(Tree)` widget for the right pane, similar to the prototype.
- [✓] **Logic** - Create a service or helper to resolve the full parameter set (including defaults) for any given `ActionType`.
- [✓] **Wiring** - The `on_tree_node_highlighted` handler must use this service to populate the `ParameterList`.

### Scenario: Clean Visual Hierarchy
> As a user, I want to see a flat list of actions without expander icons, so the interface is clean and simple.

- **Given** the TUI is rendered.
- **When** the `ActionTree` is populated with actions.
- **Then** each action MUST be displayed as a leaf node without an expander icon.

#### Deliverables
- [✓] **Wiring** - In `ReviewerApp.on_mount`, use `tree.root.add_leaf` instead of `tree.root.add` for each action.

### Scenario: Unified, Context-Aware Action Modification
> As a user, I want a single, intuitive key to edit any action, which uses a simple modal for quick changes and my full editor for complex content.

- **Given** an action is highlighted in the `ActionTree`.
- **When** I press `e` (edit/details).
- **Then** the system MUST open a `ParameterEditModal` for simple text-based actions (`EXECUTE`, `RESEARCH`).
- **And** the system MUST open my external editor for content-heavy actions (`CREATE`, `EDIT`).
- **And** after confirming any changes, the action MUST be marked as `*modified`.

#### Deliverables
- [x] **Refactor** - Consolidate the functionality of `action_edit_action` (`e`) and `action_preview` (`p`) into a single `action_edit_details` method bound to `e`. Remove the `p` binding.
- [x] **Logic** - Implement branching logic within `action_edit_details` to show a modal for simple types and launch an external editor for complex types, as seen in the prototype.
- [ ] **Logic** - Ensure the external editor workflow for `CREATE` prompts for a file path ("Save As" model).
- [ ] **Logic** - Ensure confirmation prompts are used to finalize changes and set the `modified` state on the `ActionData` object.

### Scenario: Interactive `PROMPT` Action
> As a user, when I see a `PROMPT` action, I want to provide my answer directly within the TUI, so I don't have to be prompted again during execution.

- **Given** a `PROMPT` action is highlighted.
- **When** I press `e` (edit/details).
- **Then** my external editor MUST open, populated with the AI's question as context.
- **And** after I provide my answer in the editor, save, and confirm in the TUI.
- **Then** my response MUST be stored with the action, to be used automatically during execution.

#### Deliverables
- [ ] **Logic** - Add a case to the primary `action_edit_details` handler to manage the `PROMPT` action type.
- [ ] **Domain** - Extend `ActionData` in `plan.py` with a field like `user_response: Optional[str] = None`.
- [ ] **Harness** - Add an acceptance test to verify the end-to-end flow, ensuring the stored response is used during execution.

### Scenario: Comprehensive Toggling and Navigation
> As a user, I want to use standard, efficient keybindings to select and deselect actions for execution.

- **Given** the TUI is active.
- **When** I press `a` (toggle all).
- **Then** all actions MUST be selected if any were unselected; otherwise, all actions MUST be deselected.
- **When** an action is highlighted and I press `space` or `enter`.
- **Then** its selection state MUST be toggled.

#### Deliverables
- [✓] **Logic** - The `(a)` key is wired to `action_toggle_all` with the correct logic.
- [ ] **Wiring** - Add a `space` keybinding to `ReviewerApp` that toggles the current node's selection.
- [✓] **Wiring** - `on_tree_node_selected` (triggered by `enter`) correctly toggles selection.

### Scenario: Dynamic Footer & Full Plan Viewing
> As a user, I want a dynamic footer that shows only relevant actions, and an option to view the original plan file for full context.

- **Given** the TUI is active.
- **When** I highlight a modified action.
- **Then** the `(r) Revert` binding MUST appear in the footer.
- **When** I highlight an unmodified action.
- **Then** the `(r) Revert` binding MUST NOT appear in the footer.
- **When** I press `v` (view plan).
- **Then** the complete, original plan file MUST open in my configured editor (read-only).

#### Deliverables
- [✓] **Logic** - Implemented `ReviewerApp.check_action` for conditional `(r)` binding.
- [✓] **Wiring** - The footer is refreshed on node highlight events.
- [✓] **Wiring** - The `(v)` key is wired to `action_view_plan`.

### Scenario: Step-by-Step Action Execution
> As a user, I want to execute actions one by one and see their real-time status, so I can have granular control and immediate feedback.

- **Given** a plan is loaded in the TUI.
- **When** I press the `x` key on a pending action.
- **Then** its label MUST immediately change to `[RUNNING]` in yellow.
- **And** the status bar MUST show that the action is executing.
- **When** the action completes successfully.
- **Then** its label MUST change to `[SUCCESS]` in green.
- **And** the status bar MUST show the success message.
- **When** the action fails.
- **Then** its label MUST change to `[FAILURE]` in red.
- **And** the status bar MUST show the failure message.

#### Deliverables
- [ ] **Domain** - Add a `RUNNING` state to the `ExecutionStatus` enum in `src/teddy_executor/core/domain/models/plan.py`.
- [ ] **Logic** - Refactor the `action_execute_step` handler to be a `worker` that updates the UI state to `RUNNING` *before* delegating to a real execution service.
- [ ] **Wiring** - The `action_execute_step` worker must update the UI with `SUCCESS` or `FAILURE` based on the execution result.
- [ ] **Wiring** - The handler must update the `StatusBar` at each stage of the execution lifecycle.

### Scenario: Improved Instruction Template & Auto-Save
> As a user, I want a clear instruction template and a fluid editing experience when adding messages.
- **Given** the TUI footer shows `(m) Message`.
- **When** I trigger the "Message" (`m`) workflow.
- **Then** the editor MUST open with the standard instruction marker.
- **And** the update MUST be deferred until the user submits the plan (`s`).

#### Deliverables
- [✓] **Logic** - Implemented deferred processing (`_user_message_cache`) and marker stripping.
- [✓] **Harness** - Unit test verifies marker stripping.

### Scenario: Event Logging Status Bar
> As a user, I want a persistent status bar that shows the last significant event.
- **Given** the TUI is active.
- **When** an action is triggered (e.g., editing, executing).
- **Then** a dedicated status bar at the bottom MUST display a log of the event, as shown in the prototype.

#### Deliverables
- [✓] **Wiring** - `StatusBar` widget is correctly implemented and docked at the bottom.
- [✓] **Logic** - `os.path.basename` is used for editor logging.
- [ ] **Wiring** - Ensure all user-facing action handlers (e.g., `action_edit_details`, `action_execute_step`, `action_revert`) post notifications to the `StatusBar`.

## 3. Implementation Guidelines
This slice should be implemented by a Developer, using the reference prototype as a guide for the overall structure and desired UX. The implementation must reconcile the prototype's vision with the existing codebase.

- **Header & Title:** The `ReviewerApp.on_mount` method should dynamically set the app title based on the plan's title and status emoji. The `Header` widget should be configured with `show_clock=True`.
- **Architecture:** The main screen MUST use a `Horizontal` layout containing the `ActionTree` and a new read-only `ParameterList`. Highlighting a node in the `ActionTree` MUST update the `ParameterList` to show all available parameters for that action type, including defaults.
- **Visuals:** Actions MUST be added to the `ActionTree` as leaf nodes to prevent the expander icon from showing. The `StatusBar` must be docked at the bottom and used for all event logging.
- **Keybindings:**
    - `e` (Edit/Details): Consolidate `(e)` and `(p)` bindings. This key should open a **modal** for simple parameters (`EXECUTE`, `RESEARCH`) or an **external editor** for complex content (`CREATE`, `EDIT`, `PROMPT`).
    - `x` (Execute Step): Triggers the **real execution** of the highlighted action, with UI updates for `RUNNING`, `SUCCESS`, and `FAILURE` states.
    - `v` (View Plan): Opens the original, unmodified plan file.
    - `space` / `enter`: Toggles selection of the highlighted action.
    - `a`: Toggles selection of all actions.
    - `m`: Adds a user instruction message.
    - `r`: Reverts modifications to the highlighted action (conditionally visible).
    - `s`: Submits the reviewed plan.
    - `q`: Quits and cancels the review.
- **PROMPT Workflow:** The interactive answering of `PROMPT` actions via the `(e)` key is a critical missing feature. The implementation should store the user's answer back into the `ActionData` object.
- **Prototype-Only Keys:** The `(f)` keybinding from the prototype for simulating failure is for demonstration purposes only and MUST NOT be included in the final production implementation.

## 4. Implementation Notes

-   **Header Title Logic**: Implemented dynamic title setting in `ReviewerApp.on_mount`. Refactored the logic for extracting the status emoji into a new, unit-tested helper function `extract_status_emoji` in `textual_plan_reviewer_logic.py` to improve robustness and testability.
-   **Header Clock Implementation**: Configured the `Header` widget with `show_clock=True` in `ReviewerApp.compose`. Verified its presence in acceptance tests by querying for the internal `HeaderClock` widget (imported from `textual.widgets._header`).
-   **Dual-Pane TUI Layout**: Refactored the single-pane tree into a dual-pane layout using `Horizontal` layout and `65%/35%` proportions. Introduced `ActionTree` and `ParameterList` specialized widgets.
-   **Real-time Parameter Inspection**: Implemented dynamic population of the `ParameterList` when nodes in the `ActionTree` are highlighted. Added logic to filter out verbose content fields (like `content` or `FIND`/`REPLACE` blocks) to maintain a clean inspection view.
-   **Flat Visual Hierarchy**: Migrated `ActionTree` population to use `add_leaf` to remove expander icons from a traditionally flat list of actions.

**Delta Analysis Summary:**
This slice has been updated based on a delta analysis between the reference prototype, the original slice, and the current source code (`textual_plan_reviewer.py`, `plan.py`). Key gaps identified include:

1.  **Major Layout Difference:** The current implementation is a single-pane tree. It needs to be refactored into the dual-pane (ActionTree, ParameterList) layout specified in the prototype.
2.  **Consolidate Edit/Preview:** The current `(e)` and `(p)` keybindings are confusing and overlap. They must be consolidated into a single, context-aware `(e)` binding as specified in the prototype and scenarios.
3.  **Missing `PROMPT` Workflow:** The ability to answer `PROMPT` actions interactively is not implemented and requires changes to the domain model (`ActionData`) and the TUI handler.
4.  **Incomplete Execution Feedback:** The real-time `[RUNNING]` status for executing actions is missing. This requires adding a new state to the `ExecutionStatus` enum and refactoring the execution handler into a `worker`.
5.  **Minor Gaps:** The dynamic header, use of `add_leaf`, `spacebar` binding, and comprehensive status bar notifications are also missing and have been added as explicit deliverables.
