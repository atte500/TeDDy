# Slice 00-04: TUI UX Polish and Refinements
- **Status:** Planned
- **Milestone:** [Milestone 10: Interactive Session Workflow & LLM Integration](/docs/project/milestones/10-interactive-session-and-config.md)
- **Reference Prototype:** [prototypes/tui_deferred_harvest.py](/prototypes/tui_deferred_harvest.py)

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
- **When** the `ParameterDetail` panel on the right is populated.
- **Then** it MUST display all possible parameters for that action type, showing the actual value if present, or the system's default value if not.
- **And** long parameters MUST wrap within the panel instead of causing horizontal scroll.

#### Deliverables
- [✓] **Layout** - Refactor `ReviewerApp.compose` to use a `Horizontal` layout (65/35 split).
- [✓] **Widget** - Replace `ParameterList(Tree)` with `ParameterDetail(ListView)` in `textual_plan_reviewer_widgets.py` to enable scrolling and focus.
- [✓] **Widget** - Implement `DetailItem(ListItem)` using a single `Label` to allow same-line text wrapping for long parameters.
- [✓] **Logic** - Create a service or helper to resolve the full parameter set (including defaults) for any given `ActionType`.
- [ ] **Wiring** - Update `on_mount_logic` and `_update_detail_view` in `textual_plan_reviewer_logic.py` to populate the `ParameterDetail` (ListView) instead of the old Tree.
- [ ] **Wiring** - Implement `on_focus` in `ReviewerApp` to automatically highlight the first item in the list when the user tabs into the right pane.

### Scenario: Clean Visual Hierarchy
> As a user, I want to see a flat list of actions without expander icons, so the interface is clean and simple.

- **Given** the TUI is rendered.
- **When** the `ActionTree` is populated with actions.
- **Then** each action MUST be displayed as a leaf node without an expander icon.

#### Deliverables
- [✓] **Wiring** - In `ReviewerApp.on_mount`, use `tree.root.add_leaf` instead of `tree.root.add` for each action.

### Scenario: Non-Blocking Deferred Editing (Deferred Harvest)
> As a user, I want my editor to open instantly and non-blockingly, so I can continue browsing the plan while I make changes.

- **Given** an action is highlighted in the `ActionTree`.
- **When** I press `e` (Edit).
- **Then** the system MUST launch my external editor without `--wait` (for GUIs) and without suspending the TUI.
- **And** it MUST NOT prompt for confirmation or wait for the editor to close.
- **When** I click `(s) Submit`.
- **Then** the system MUST harvest (read) the content from all open temporary files created during the session and apply them to the plan before exiting.

#### Deliverables
- [ ] **Logic** - Refactor `ConsoleToolingHelper` to remove `--wait` and blocking heuristics for `code` and other GUI editors.
- [ ] **Domain** - Add `pending_temp_file: Optional[str]` to `ActionData` to track temporary files for deferred harvesting.
- [ ] **Logic** - Implement branched editing in `action_edit_details`: Use `ParameterEditModal` (TUI Input) for simple parameters (e.g., `timeout`, `match_all`) and `launch_editor` (External) only for content-heavy fields (`command`, `content`, `message`).
- [ ] **Logic** - Ensure `*modified` tag is applied as a suffix only after user confirmation for external edits, or immediately for TUI modal edits.
- [ ] **Logic** - Update `action_submit` to iterate through all actions and the user message cache, reading and applying any `pending_temp_file` content before deletion.

### Scenario: High-Density UI & Post-Execution Feedback
> As a user, I want a clear summary of actions in the tree and a detailed parameter view that shows defaults and execution results.

- **Given** the TUI is active.
- **Then** the `ActionTree` labels MUST be formatted as `TYPE: description`.
- **And** for `PROMPT` actions, the label MUST show the first 60 characters of the message.
- **When** an action is highlighted.
- **Then** the `ParameterList` (right pane) MUST display all valid parameters for that action type, populated with current values or fallbacks from the `IConfigService` (e.g., `timeout` defaults to 30.0).
- **When** an action has been executed.
- **Then** the `ParameterList` MUST switch to displaying the `ActionLog` (Status, Details, Failed Command) for that action.

#### Deliverables
- [ ] **Logic** - Update `format_node_label` to use the `TYPE: description` format and truncated `PROMPT` messages.
- [ ] **Wiring** - Update `_update_detail_view` to populate the `ParameterList` from a canonical map of action keys per type.
- [ ] **Wiring** - Update `_update_detail_view` to render the `ActionLog` instead of parameters if `action.executed` is true.
- [ ] **Style** - Replace the `ParameterList(Tree)` in the right pane with a `VerticalScroll` container. Mount parameters as `Static` widgets with `height: auto;` to enable native Textual text wrapping for long paths and commands.
- [ ] **Standardization** - Implement a standardized `StatusBar` notification format: `[TIME] ACTION: STATUS - DETAIL` (e.g., `[09:42] EXECUTE: SUCCESS - poetry install`).
- [ ] **Logic** - Ensure that manual execution of a `PROMPT` action via the `(x)` key triggers the "Reply in Editor" workflow (identical to the console mode's `(e)` reply loop) instead of hanging. This should capture the response and mark the action as `SUCCESS`.

### Scenario: Interactive `PROMPT` Action [✓] Verified
> As a user, when I see a `PROMPT` action, I want to provide my answer directly within the TUI, so I don't have to be prompted again during execution.

- **Given** a `PROMPT` action is highlighted.
- **When** I press `e` (Edit).
- **Then** my external editor MUST open, populated with the AI's question as context.
- **And** after I provide my answer in the editor, save, and confirm in the TUI.
- **Then** my response MUST be stored with the action, to be used automatically during execution.

#### Deliverables
- [✓] **Logic** - Add a case to the primary `action_edit_details` handler to manage the `PROMPT` action type.
- [✓] **Domain** - Extend `ActionData` in `plan.py` with a field like `user_response: Optional[str] = None`.
- [✓] **Harness** - Add an acceptance test to verify the end-to-end flow, ensuring the stored response is used during execution.

### Scenario: Comprehensive Toggling and Navigation
> As a user, I want to use standard, efficient keybindings to select and deselect actions for execution.

- **Given** the TUI is active.
- **When** I press `a` (toggle all).
- **Then** all actions MUST be selected if any were unselected; otherwise, all actions MUST be deselected.
- **When** an action is highlighted and I press `space` or `enter`.
- **Then** its selection state MUST be toggled.

#### Deliverables
- [✓] **Logic** - The `(a)` key is wired to `action_toggle_all` with the correct logic.
- [✓] **Wiring** - Add a `space` keybinding to `ReviewerApp` that toggles the current node's selection.
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

### Scenario: Step-by-Step Action Execution [✓] Verified
> As a user, I want to execute actions one by one and see their real-time status, so I can have granular control and immediate feedback.

- **Given** a plan is loaded in the TUI.
- **When** I press the `x` key on a pending action.
- **Then** its label MUST immediately change to `[RUNNING]` in blue.
- **And** the status bar MUST show that the action is executing.
- **When** the action completes successfully.
- **Then** its label MUST change to `[SUCCESS]` in green.
- **And** the status bar MUST show the success message.
- **When** the action fails.
- **Then** its label MUST change to `[FAILURE]` in red.
- **And** the status bar MUST show the failure message.

#### Deliverables
- [✓] **Domain** - Add a `RUNNING` state to the `ExecutionStatus` enum in `src/teddy_executor/core/domain/models/plan.py`.
- [✓] **Logic** - Refactor the `action_execute_step` handler to be a `worker` that updates the UI state to `RUNNING` *before* delegating to a real execution service.
- [✓] **Wiring** - The `action_execute_step` worker must update the UI with `SUCCESS` or `FAILURE` based on the execution result.
- [✓] **Wiring** - The handler must update the `StatusBar` at each stage of the execution lifecycle.
- [✓] **Orchestration** - Refactor `ExecutionOrchestrator` to support manual execution persistence and sequential skipping. Verified with integration tests.

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
- [✓] **Wiring** - Ensure all user-facing action handlers (e.g., `action_edit_details`, `action_execute_step`, `action_revert`) post notifications to the `StatusBar`.

## 3. Implementation Guidelines
This slice should be implemented by a Developer, using the reference prototype as a guide for the overall structure and desired UX. The implementation must reconcile the prototype's vision with the existing codebase.

- **Header & Title:** The `ReviewerApp.on_mount` method should dynamically set the app title based on the plan's title and status emoji. The `Header` widget should be configured with `show_clock=True`.
- **Architecture:** The main screen MUST use a `Horizontal` layout containing the `ActionTree` and a new read-only `ParameterList`. Highlighting a node in the `ActionTree` MUST update the `ParameterList` to show all available parameters for that action type, including defaults.
- **Visuals:** Actions MUST be added to the `ActionTree` as leaf nodes to prevent the expander icon from showing. The `StatusBar` must be docked at the bottom and used for all event logging.
- **Keybindings:**
    - `e` (Edit): Consolidate `(e)` and `(p)` bindings. This key should open a **modal** for simple parameters (`EXECUTE`, `RESEARCH`) or an **external editor** for complex content (`CREATE`, `EDIT`, `PROMPT`).
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

-   **ListView Migration**: Replaced the Tree-based `ParameterList` with a `ParameterDetail` widget inheriting from `ListView`. This change enables better focus management and simplifies the logic for rendering complex, wrapping text.
-   **Text Wrapping**: Implemented `DetailItem` using a single `Label` within a `ListItem`. By setting `width: 100%` and `height: auto` on the `Label` via CSS, Textual handles multi-line wrapping for long paths or commands automatically.
-   **Header Title Logic**: Implemented dynamic title setting in `ReviewerApp.on_mount`. Refactored the logic for extracting the status emoji into a new, unit-tested helper function `extract_status_emoji` in `textual_plan_reviewer_logic.py` to improve robustness and testability.
-   **Header Clock Implementation**: Configured the `Header` widget with `show_clock=True` in `ReviewerApp.compose`. Verified its presence in acceptance tests by querying for the internal `HeaderClock` widget (imported from `textual.widgets._header`).
-   **Dual-Pane TUI Layout**: Refactored the single-pane tree into a dual-pane layout using `Horizontal` layout and `65%/35%` proportions. Introduced `ActionTree` and `ParameterList` specialized widgets.
-   **Real-time Parameter Inspection**: Implemented dynamic population of the `ParameterList` when nodes in the `ActionTree` are highlighted. Added logic to filter out verbose content fields (like `content` or `FIND`/`REPLACE` blocks) to maintain a clean inspection view.
- **Flat Visual Hierarchy**: Migrated `ActionTree` population to use `add_leaf` to remove expander icons from a traditionally flat list of actions.
-   **Interactive PROMPT Handling**: Extended the `ActionData` domain model with a `user_response` field. Implemented `preview_prompt` in the previews adapter to allow answering questions via an external editor. This response is stored in the domain model and is intended to be used by the executor to bypass redundant prompts.
-   **Concurrent "Save As" Workflow**: Refactored `preview_create` and `preview_edit` to use `asyncio.gather` for launching the modification tool (editor or diff viewer) and the confirmation/path prompt concurrently. This ensures the TUI remains interactive and prompts the user while they are making changes, satisfying the "Unified, Context-Aware Action Modification" requirements. Verified the non-blocking behavior with dedicated concurrency unit tests for both `CREATE` and `EDIT` actions.
-   **Step-by-Step Execution Worker**: Refactored the TUI execution handler into a background worker using Textual's `@work` decorator. Introduced the `RUNNING` state in the domain model to allow for immediate visual feedback (blue label) and persistent status updates.
- **Real Execution Wiring**: Integrated the `ActionDispatcher` service into the TUI adapter. The execution worker now performs real filesystem and shell operations in a separate thread using `anyio.to_thread.run_sync`, ensuring the TUI remains responsive while providing real-time feedback on action outcomes.
- **Manual Execution Persistence**: Enhanced `ExecutionOrchestrator` to recognize and preserve `ActionLog`s from actions already executed in the TUI. This ensures that the final `ExecutionReport` accurately reflects the outcome of a mixed manual/automatic execution session.
- **Sequential Halt for Manual Failures**: Implemented logic in `ExecutionOrchestrator` to automatically skip subsequent actions if a previous action (whether manual or automatic) failed, maintaining state consistency.

**Delta Analysis Summary:**
The following technical gaps were identified between the production code and the finalized prototype:

1.  **Domain Expansion (`plan.py`):**
    - [✓] **Contract** - Add `pending_temp_file: Optional[str] = None` to `ActionData` to track deferred content.

## ## Implementation Notes
### Deliverable: Domain Expansion (plan.py)
- Added `pending_temp_file: Optional[str] = None` to the `ActionData` dataclass to support the deferred harvesting workflow.
- Verified with unit tests (since deleted as part of the atomic cleanup).
2.  **Deadlock Resolution (`textual_plan_reviewer.py`):**
    - [ ] **Logic** - Refactor `ReviewerApp.push_screen_wait`. The current `asyncio.Future` implementation deadlocks. It MUST use the native Textual `await self.push_screen(screen)` wait mechanism (or a thread-safe callback) ensuring it is only awaited from within `@work` handlers.
3.  **Layout & Wrapping (`textual_plan_reviewer_widgets.py` & `logic.py`):**
    - [ ] **Wiring** - Replace `ParameterList(Tree)` with `ParameterDetail(ListView)`.
    - [ ] **Logic** - Implement `DetailItem(ListItem)` using a single `Label` for native text wrapping.
    - [ ] **Logic** - Update `format_node_label` in `logic.py` to truncate summaries to 60 characters to maintain density in the dual-pane view.
4.  **Focus & Modals (`textual_plan_reviewer_widgets.py` & `textual_plan_reviewer.py`):**
    - [ ] **Logic** - Add `on_mount` focus logic to `ConfirmScreen`, `PathInputScreen`, and `ParameterEditModal`.
    - [ ] **Wiring** - Add `EnterConfirmOverlay` for the `PROMPT` workflow to allow intuitive `enter` confirmation.
    - [ ] **Wiring** - Update `ReviewerApp.on_focus` to correctly use `event.control` (not `event.node`) to trigger auto-selection in the right pane.
5.  **Deferred Harvesting Implementation (`textual_plan_reviewer.py` & `previews.py`):**
    - [ ] **Logic** - Refactor `launch_editor` in `logic.py` to return the temp path for `ActionData.pending_temp_file` rather than just the content, enabling the deferred harvest on `submit`.
    - [ ] **Wiring** - Update `action_submit` to iterate through all actions and harvest any `pending_temp_file` content before exiting.
6.  **Action Handlers (`textual_plan_reviewer_logic.py`):**
    - [ ] **Logic** - Update `execute_step_logic` to trigger the editor-reply loop when a `PROMPT` action is executed manually.
