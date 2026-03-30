# Slice 00-04: TUI & UX Polish Refinements
- **Status:** Planned
- **Milestone:** [Milestone 10: Interactive Session Workflow & LLM Integration](/docs/project/milestones/10-interactive-session-and-config.md)

## 1. Business Goal
To resolve specific UX frictions and regressions in the TUI and planning workflow, ensuring a seamless, high-visibility experience that respects user configuration.

## 2. Scenarios

### Scenario: Editor Configuration & VS Code Wait [ ]
> As a user, I want to configure my preferred editor in `config.yaml` and have it work correctly with the TUI so that I can edit messages and actions without the TUI resuming prematurely.

- **Given** `editor: code` is set in `.teddy/config.yaml`.
- **When** I trigger an edit action in the TUI (`m`, `p`, or `v`).
- **Then** the system MUST use `code --wait` to launch the editor.
- **And** the TUI MUST remain suspended until the VS Code instance is closed.

#### Deliverables
- [ ] **Contract** - Update `IConfigService` or `ConsoleToolingHelper` to support an `editor` setting.
- [ ] **Logic** - Update `ConsoleToolingHelper.find_editor` to return a `List[str]` (command + args) instead of a single string.
- [ ] **Logic** - If `code` is the detected/configured editor, automatically append `--wait` to the command list.
- [ ] **Logic** - Update `ReviewerApp._launch_editor` to use the command list with `self._system_env.run_command`.

### Scenario: Reliable "View Plan" (v) [ ]
> As a user in manual execution mode, I want to view the plan in my editor so that I can verify the context even when the plan is provided via the clipboard.

- **Given** I run `teddy execute` with `--plan-content`.
- **When** I press `v` in the TUI.
- **Then** the plan content MUST open in the external editor.

#### Deliverables
- [ ] **Logic** - Update `ReviewerApp.action_view_plan` to ensure it falls back to reading the `plan_path` even if the internal plan object was passed by value (leveraging the temp file path set by the orchestrator).

### Scenario: Mandatory "Saved?" Confirmation [ ]
> As a user, I want a final confirmation after editing in an external editor so that I don't accidentally apply unsaved changes or lose progress.

- **Given** I am in any "Preview/Modify" or "Add Message" workflow in the TUI.
- **When** the external editor closes.
- **Then** the TUI MUST display the `ConfirmScreen` ("Have you finished editing and saved?").
- **And** changes MUST ONLY be applied if I select `y`.

#### Deliverables
- [ ] **Logic** - Update `ReviewerApp.action_add_message` to be an `@work` async method and await `ConfirmScreen`.
- [ ] **Logic** - Ensure all `_preview_*` methods in `ReviewerApp` correctly await and check the result of `ConfirmScreen`.

### Scenario: Logical Log Sequencing [ ]
> As a user, I want to see the "Planning Turn" message only after I've provided my instructions so that the UI reflects the actual sequence of events.

- **Given** I am in an interactive session.
- **When** a planning turn starts.
- **Then** the message `[01] Planning Turn with pathfinder...` MUST ONLY appear after the `user_request` has been resolved (either via CLI flag, lookback, or TUI input).

#### Deliverables
- [ ] **Logic** - Move the display of the progress message in `SessionPlanner.trigger_new_plan` to *after* the `PlanningService.generate_plan` call or within it, ensuring it follows instruction capture.

### Scenario: Clean Telemetry Formatting [ ]
> As a developer, I want telemetry to be concise and well-formatted so that I can quickly assess cost and tokens without visual noise.

- **Given** a plan has been generated.
- **When** telemetry is displayed.
- **Then** `Tokens` MUST be formatted using `k` units (e.g., `37.7k`).
- **And** `Model` MUST be dedented (no leading spaces).
- **And** `Context` and `Session Cost` lines MUST be removed from the planning output (Session Cost remains in the execution report).

#### Deliverables
- [ ] **Logic** - Update `PlanningService._log_telemetry` to format token counts (e.g., `count / 1000` rounded to 1 decimal).
- [ ] **Logic** - Update `SessionPlanner._display_planning_telemetry` to remove leading spaces from "Model".
- [ ] **Logic** - Remove `Context` and `Session Cost` display from `SessionPlanner._display_planning_telemetry`.

### Scenario: Direct Instruction Control [ ]
> As a user, I want to control the session loop exclusively via instructions or the `m` binding so that I'm not interrupted by redundant prompts.

- **Given** I am in an interactive session loop.
- **When** the `PlanningService` looks for instructions.
- **Then** it MUST NOT use `self._user_interactor.ask_question` as a fallback.
- **And** an empty/null instruction MUST trigger an exit from the session loop.

#### Deliverables
- [ ] **Logic** - Remove the interactive prompt fallback from `PlanningService.generate_plan`.
- [ ] **Logic** - Ensure `SessionOrchestrator` or `SessionCLIHandlers` gracefully handles the `None` return from `resume` (caused by empty instructions) by exiting the loop.

## 3. Implementation Guidelines

### Editor & Tooling
- Modify `ConsoleToolingHelper` to accept `IConfigService` in its constructor.
- Update `find_editor` to:
  1. Check `config.get_setting("editor")`.
  2. Fallback to `VISUAL`/`EDITOR`.
  3. Fallback to discovery (`code`, `nano`, `vim`).
  4. Return `[cmd, "--wait"]` if `cmd` is `code`.

### TUI Confirmations
- Every `@work` method in `ReviewerApp` that triggers `_launch_editor` (including `action_add_message`) must become a `ModalScreen` awaiter.

### Telemetry
- Use `f"{count/1000:.1f}k"` for token formatting.
- Ensure `PlanningService` and `SessionPlanner` use consistent, dedented output for CLI/TUI display.