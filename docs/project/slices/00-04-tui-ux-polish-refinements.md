# Slice 00-04: TUI & UX Polish Refinements
- **Status:** Planned
- **Milestone:** [Milestone 10: Interactive Session Workflow & LLM Integration](/docs/project/milestones/10-interactive-session-and-config.md)

## 1. Business Goal
To resolve specific UX frictions and regressions in the TUI and planning workflow, ensuring a seamless, high-visibility experience that respects user configuration.

## 2. Scenarios

### Scenario: Editor Configuration & Default [✓] Verified
> As a user, I want to configure my preferred editor in `config.yaml` or use a sensible default so that I can edit messages and actions using any arbitrary editor command.

- **Given** I trigger an edit action in the TUI (`m`, `p`, or `v`).
- **When** the system looks for an editor.
- **Then** it MUST check `config.yaml`, then `VISUAL`/`EDITOR` env vars.
- **And** it MUST default to `code` if no other configuration is found.
- **And** it MUST support arbitrary command strings (e.g., `zed --wait` or `code`).

#### Deliverables
- [✓] **Contract** - Update `IConfigService` or `ConsoleToolingHelper` to support an `editor` setting.
- [✓] **Logic** - Update `ConsoleToolingHelper.find_editor` to support parsing arbitrary command strings into a `List[str]`.
- [✓] **Logic** - Implement fallback chain: Config -> Env -> `code` -> `nano`.
- [✓] **Logic** - Update `ReviewerApp._launch_editor` to use the command list with `self._system_env.run_command`.

### Scenario: Reliable "View Plan" (v) [✓] Verified
> As a user in manual execution mode, I want to view the plan in my editor so that I can verify the context even when the plan is provided via the clipboard.

- **Given** I run `teddy execute` with `--plan-content`.
- **When** I press `v` in the TUI.
- **Then** the plan content MUST open in the external editor.

#### Deliverables
- [✓] **Logic** - Update `ReviewerApp.action_view_plan` to ensure it falls back to reading the `plan_path` even if the internal plan object was passed by value (leveraging the temp file path set by the orchestrator).

### Scenario: Non-Blocking "Immediate Prompt" Workflow [ ]
> As a user, I want to trigger an edit and have the confirmation prompt waiting for me in the TUI so I can save and confirm without re-navigating.

- **Given** I am in the TUI.
- **When** I press `e` (Edit) on an action.
- **Then** the external editor MUST launch in a non-blocking way (no `--wait` for GUIs).
- **And** the TUI MUST IMMEDIATELY display a confirmation prompt (e.g., "Editing... Save changes? (y/n)") for the selected context.
- **And** it MUST NOT wait for the editor process to exit or the tab to close.
- **And** when I press `y`, the TUI MUST read the temp file and update the state to `*modified`.
- **And** if I press `n`, it MUST discard the edit session and cleanup.

#### Deliverables
- [ ] **Cleanup** - Remove `ConfirmScreen` and consolidate `m`/`p` into `e` (Edit).
- [ ] **Logic** - Refactor `ReviewerApp._launch_editor` to launch the editor as a background task and immediately trigger a non-blocking inline prompt.
- [ ] **Logic** - Ensure the `y` response to the prompt triggers the file read and state update (Action or Global Message).
- [ ] **Logic** - Update `ReviewerApp.action_submit` to perform a final sync check of all active editor paths before exit.

### Scenario: Revert Modifications (Undo) [ ]
> As a user, I want to be able to undo my manual modifications to an action so that I can revert to the AI's original proposal.

- **Given** an action is marked as `*modified` in the TUI.
- **When** I press `r` (Revert) on that node.
- **Then** the action's `modified` flag MUST be cleared.
- **And** its parameters MUST be restored to their original state from the plan.
- **And** the corresponding temp file (if any) MUST be updated or deleted.

#### Deliverables
- [ ] **Logic** - Add an `r` binding to `ReviewerApp` for `revert`.
- [ ] **Logic** - Implement `action_revert` to restore original state and cleanup tracking.

### Scenario: Logical Log Sequencing [ ]
> As a user, I want to see the "Planning Turn" message only after I've provided my instructions so that the UI reflects the actual sequence of events.

- **Given** I am in an interactive session.
- **When** a planning turn starts.
- **Then** the message `[01] Planning Turn with pathfinder...` MUST ONLY appear after the `user_request` has been resolved (either via CLI flag, lookback, or TUI input).

#### Deliverables
- [ ] **Logic** - Move the display of the progress message in `SessionPlanner.trigger_new_plan` to *after* the `PlanningService.generate_plan` call or within it, ensuring it follows instruction capture.

### Scenario: Enhanced Visibility (Header Replacement) [ ]
> As a user, I want the TUI header to show the plan's title and status instead of "ReviewerApp" so I know exactly what I am reviewing.

- **Given** I am in the TUI (`ReviewerApp`).
- **When** the header is displayed.
- **Then** the central text MUST be the Plan Title prefixed with its status emoji (e.g., "🟢 Implementation: Add User Auth").
- **And** it MUST NOT say "ReviewerApp".
- **And** in `--console` mode, the progress message MUST include the status emoji (red, green, yellow) matching the plan's status.

#### Deliverables
- [ ] **Logic** - Update `ReviewerApp` to override the default `title` property or update the `Header` widget to display `[Emoji] {plan.title}`.
- [ ] **Logic** - Update `SessionOrchestrator._display_planning_progress` or `cli_helpers` to resolve and display the status emoji in console mode.

### Scenario: Improved Instruction Template [ ]
> As a user, I want a clear instruction template when adding messages so that I know where to provide my input.

- **Given** I trigger the "Add Message" (`m`) workflow.
- **When** the editor opens.
- **Then** it MUST contain a descriptive header: "Provide message above this line --- START OF FILE text/plain ---".

#### Deliverables
- [ ] **Logic** - Update `ReviewerApp.action_add_message` to prepend the instruction template to the temporary file content.
- [ ] **Logic** - Ensure the template is stripped before saving the final message.

### Scenario: Clean Telemetry Formatting [ ]
... (as before) ...

### Scenario: AI-Driven Continuity (Proceed on Empty) [ ]
> As a user, I want the AI to proceed with planning based on the execution report even if I don't provide explicit instructions.

- **Given** I am in an interactive session.
- **When** I provide an empty/null instruction.
- **Then** the `PlanningService` MUST NOT exit the loop.
- **And** it MUST proceed to call the LLM using the current context (including the `report.md` of the previous turn) as the primary instruction.

#### Deliverables
- [ ] **Logic** - Update `PlanningService.generate_plan` to treat empty input as a valid "Proceed with Context" signal.
- [ ] **Logic** - Ensure `SessionOrchestrator` does not interpret empty return values from planning as a "Cancel" signal unless explicitly triggered by a `q` (Quit) equivalent.

## 3. Implementation Guidelines

### Editor & Tooling
- Modify `ConsoleToolingHelper` to accept `IConfigService` in its constructor.
- Update `find_editor` to:
  1. Check `config.get_setting("editor")`.
  2. Fallback to `VISUAL`/`EDITOR`.
  3. Fallback to discovery (`code`, `nano`, `vim`).
  4. Use `code` as the primary default if available on the path.
  5. Parse the resulting command string using `shlex.split` to support arguments.

### TUI Confirmations
- Every `@work` method in `ReviewerApp` that triggers `_launch_editor` (including `action_add_message`) must become a `ModalScreen` awaiter.

### Telemetry
- Use `f"{count/1000:.1f}k"` for token formatting.
- Ensure `PlanningService` and `SessionPlanner` use consistent, dedented output for CLI/TUI display.

## 6. Implementation Notes

### Scenario: Editor Configuration & Default
- **ConsoleToolingHelper.find_editor**: Refactored to return `Optional[List[str]]` instead of a string. This allows for direct passing to `subprocess.run` (via `SystemEnvironment`) without manual splitting in calling adapters.
- **Path Resolution**: The first element of the command list (the executable) is now explicitly resolved via `ISystemEnvironment.which` to ensure absolute paths are used when available, preventing PATH-related execution failures in sub-shells.

### Scenario: Reliable "View Plan" (v)
- **Robust Fallback**: `ReviewerApp.action_view_plan` now implements a tiered fallback: First, it tries the physical `plan_path` (which the orchestrator ensures exists even for clipboard plans). Second, it uses `plan.raw_content`. Finally, it falls back to a basic string serialization if all else fails.

### Scenario: Mandatory "Saved?" Confirmation
- **Unified Modification Loop**: Every workflow that modifies the plan (`Add Message`, `Preview/Modify`) now uses an async `@work` loop that awaits `ConfirmScreen` before applying changes.
- **EDIT Preview Diffs (Side-by-Side)**: The `_preview_edit` method now supports true side-by-side diffing. If a diff tool (like `code --diff`) is detected, it creates two temporary files (`.before` and `.after`) and launches the viewer. The `--wait` flag is used for VS Code to prevent race conditions during file cleanup.
- **Non-Blocking Clipboard**: Refactored `echo_and_copy` to use a completely detached, daemonized thread for clipboard operations without `join()`. This ensures the CLI can exit instantly even if `pyperclip` or the underlying OS clipboard provider (e.g., `pbcopy` or `xclip`) hangs.
- **Test Robustness**: Updated TUI unit and acceptance tests to use unique temporary file paths per operation, resolving `OSError: [Errno 9] Bad file descriptor` caused by mock overlap during concurrent file cleanup.
- **TUI Test Mocking (Sync vs Async CM)**: Resolved persistent `AssertionError` in `test_tui_view_plan_robustness.py` by ensuring the `suspend()` mock returns a synchronous context manager (`@contextmanager`) instead of an asynchronous one, matching the application's usage of a standard `with` statement.
