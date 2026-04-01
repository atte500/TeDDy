# Slice 00-04: TUI UX Polish and Refinements
- **Status:** Planned
- **Milestone:** [Milestone 10: Interactive Session Workflow & LLM Integration](/docs/project/milestones/10-interactive-session-and-config.md)
- **Reference Prototype:** [prototypes/tui_canonical_final.py](/prototypes/tui_canonical_final.py)

## 1. Business Goal
To refine the plan review TUI by implementing a more robust interaction model based on user feedback. The goal is to provide clear visual feedback for action status (pending, modified, executed) and a streamlined editing workflow that uses the user's external editor.

## 2. Scenarios

### Scenario: Clear Action Status and Execution Flow
> As a user, I want to see the status of each action at a glance and step through execution, getting clear feedback on success or failure.

- **Given** a plan is loaded in the TUI.
- **When** an action is executed successfully via the `x` key.
- **Then** its checkbox MUST be replaced with `[SUCCESS]` in green.
- **When** an action fails execution (simulated via the `f` key in prototype).
- **Then** its checkbox MUST be replaced with `[FAILURE]` in red.

#### Deliverables
- [✓] **Logic** - The `Action` domain model must track its execution state (`PENDING`, `SUCCESS`, `FAILURE`).
- [✓] **Logic** - The node update logic must render the label with appropriate colors based on the state.

## 6. Implementation Notes

### Scenario: Clear Action Status and Execution Flow
- **Deliverable: Action State Tracking**: Added `ExecutionStatus` string-based Enum to `plan.py` to match the existing `ActionType` pattern. Extended `ActionData` with `executed: bool` (default False) and `state: ExecutionStatus` (default PENDING). Verified with unit tests.
- **Deliverable: Node Label Rendering**: Updated `ReviewerApp._format_node_label` to use rich color tags (`[green]`, `[red]`) when an action is executed. Note: Accessed `ExecutionStatus.value` explicitly in f-strings to avoid `EnumMember` stringification (e.g., `ExecutionStatus.SUCCESS` vs `SUCCESS`).
- [ ] **Wiring** - The `(x)` keybinding should trigger state changes and a UI refresh.

### Scenario: External Editor Integration for Modifications
> As a user, when I want to edit or review the details of an action, I want to use my main, configured editor for a powerful and familiar experience.

- **Given** an `EDIT` or `CREATE` action is highlighted.
- **When** I press `e` (for "edit/details").
- **Then** the system MUST open my configured external editor with the relevant content (e.g., proposed content for a `CREATE`, a diff for an `EDIT`).
- **And** the TUI MUST display a confirmation prompt (`Submit manual changes? (y/n)`).
- **And** if I confirm, the action in the list MUST be marked as modified (e.g., `*modified`).

#### Deliverables
- [ ] **Logic** - Implement an `edit_action` handler that correctly identifies the editor, prepares content in a temporary file, and launches a non-blocking subprocess.
- [ ] **Wiring** - Wire the `(e)` key to this handler.
- [ ] **Logic** - The `Action` model must track a `modified` boolean state.

### Scenario: Dynamic Footer & Revert (r)
> As a user, I want to revert manual modifications, but only see the option when it's applicable.

- **Given** the TUI tree is rendered.
- **When** I move the cursor (`on_tree_node_highlighted`).
- **Then** the `(r) Revert` binding MUST only appear in the footer if the current action is `*modified`.

#### Deliverables
- [ ] **Logic** - Implement `ReviewerApp.check_action(action, parameters)` to conditionally enable/disable the `revert` binding.
- [ ] **Wiring** - Refresh footer bindings on every node highlight event.

### Scenario: Improved Instruction Template & Auto-Save
> As a user, I want a clear instruction template and a fluid editing experience when adding messages.

- **Given** the TUI footer shows `(m) Message`.
- **When** I trigger the "Message" (`m`) workflow.
- **Then** the editor MUST open with the existing message content followed by the standard marker: `\n\n<!-- Please enter your message above this line. -->`.
- **And** the system MUST defer reading and saving the message until the user submits the entire plan (pressing `s`).
- **And** upon submission, the system MUST read the file, strip the marker, and finalize the message automatically.

### Scenario: Event Logging Status Bar
> As a user, I want a persistent status bar that shows the last significant event.

- **Given** the TUI is active.
- **When** an action is triggered (e.g., launching an editor or executing a command).
- **Then** a dedicated status bar at the bottom MUST display the event details (e.g., `LAUNCHING: code /tmp/file.md`).
- **And** the log MUST use the `basename` of the editor (e.g., `code` instead of `/usr/bin/code`).
- **And** for GUI editors (like VS Code), the launch MUST be non-blocking (`subprocess.Popen`), ensuring the TUI remains responsive.

#### Deliverables
- [ ] **Wiring** - Implement a `Vertical` container for the main UI to guarantee `StatusBar` visibility at the bottom.
- [ ] **Logic** - Implement `StatusBar.notify(message: str)` to update this bar consistently without italics.
- [ ] **Logic** - Define `INSTRUCTION_MARKER` constant in `ReviewerApp`: `"\n\n<!-- Please enter your message above this line. -->"`.
- [ ] **Logic** - Implement workspace persistence: cache temporary file paths in a dictionary to ensure subsequent edits to the same message/action preserve previous content.
- [ ] **Logic** - Implement deferred processing: perform final reading and `INSTRUCTION_MARKER` stripping only during `action_submit`.
- [ ] **Harness** - Add a unit test verifying that content after the marker is correctly discarded during plan submission.

## 3. Implementation Guidelines
This slice should be implemented by a Developer, using the reference prototype as a guide for the overall structure and desired UX.

### Prototype Supplement Notes
The provided prototype at `prototypes/tui_batch_a_polish.py` is a high-fidelity guide but has known imperfections that MUST be addressed during implementation:
- **Prototype-Only Keys:** The `(f)` keybinding for simulating failure is for demonstration purposes only and MUST NOT be included in the final production implementation.
- **`EDIT` Workflow:** The prototype's `e` key launches a `subprocess.Popen` but the confirmation (`PromptOverlay`) is the critical part of the flow. The production implementation needs to ensure this is robust.
- **Parameter Editing:** The prototype does not include a dual-pane layout or a modal for editing individual parameters. This functionality MUST be added. Changes made via a parameter edit modal must correctly mark the parent action as `*modified`.
- **Keybindings:** The prototype's keybinding logic must be updated. The final implementation MUST allow **both `space` and `enter`** to toggle the selection of the highlighted action when the main action list is focused.
- **State Persistence:** The prototype does not persist changes from the `ParameterEditModal`. The production code must ensure that edits made in the modal are saved back to the `Action` data model and correctly reflected in the UI.
- **File Previews:** The prototype's external editor flow for `(e)` opens empty temporary files. The production version MUST populate these files with the correct proposed content for `CREATE` or a side by side diff for `EDIT`.
- **Parameter Editing:** The prototype incorrectly uses the external editor for all action types. The final implementation MUST use a TUI modal for editing simple parameters (like an `EXECUTE` command), reserving the external editor flow for heavy content actions like `CREATE` and `EDIT`.
- **Toggle All:** The `(a) Toggle All` functionality in the current version should be preserved.
