# Slice 09-08: TUI & UX Polish
- **Status:** Planned
- **Milestone:** [Milestone 09: Interactive Session Workflow & LLM Integration](/docs/project/milestones/09-interactive-session-and-config.md)
- **Specs:** [Interactive Session Workflow](/docs/project/specs/interactive-session-workflow.md)

## 1. Business Goal
To enable the interactive TUI for all execution modes and polish the session workflow to provide better visibility, a continuous conversational loop, and relaxed but safe action isolation.

## 2. Acceptance Criteria (Scenarios)

### Scenario: UI Mode Toggling (TUI vs. Console) [ ]
- **Given** the configuration `ui_mode: "console"` is set in `.teddy/config.yaml`.
- **When** I run a plan.
- **Then** the system MUST use a sequential `ConsolePlanReviewer`.
- **Given** the flag `--tui` is passed via CLI.
- **When** I run a plan.
- **Then** the system MUST override the config and use the `TextualPlanReviewer`.

#### Deliverables
- [ ] **Console Reviewer:** Implement `ConsolePlanReviewer` (in `src/teddy_executor/adapters/inbound/`) that handles sequential action approval via standard `typer.confirm`.
- [ ] **Config Logic:** Update `YamlConfigAdapter` and `ConfigService` to support a `ui_mode` setting (defaulting to `tui`).
- [ ] **Dynamic Wiring:** Update `src/teddy_executor/container.py` to register the correct `IPlanReviewer` implementation based on configuration.
- [ ] **CLI Flags:** Update `execute`, `start`, and `resume` commands in `__main__.py` to support `--tui / --no-tui` flags.

### Scenario: Hide PRUNE in Manual TUI [ ]
- **Given** I am running a manual CLI execution (e.g., `teddy execute plan.md`).
- **And** the plan contains a `PRUNE` action.
- **When** the TUI opens.
- **Then** the `PRUNE` action MUST NOT be visible in the tree.
- **And** the `PRUNE` action MUST be automatically marked as `SKIPPED` in the execution report.

#### Deliverables
- [ ] **TUI Filtering:** Update `ReviewerApp` in `textual_plan_reviewer.py` to accept an `is_session` flag and filter out `PRUNE` actions from the UI tree if `False`.
- [ ] **Context Passing:** Update `ExecutionOrchestrator` to detect session context (presence of `plan_path`) and pass the `is_session` hint to the reviewer.

### Scenario: Continuous Session Loop [ ]
- **Given** I am in an interactive session.
- **When** a plan execution completes.
- **Then** the CLI MUST NOT exit.
- **And** it MUST automatically transition to the next turn and prompt for new instructions.

#### Deliverables
- [ ] **Orchestration Loop:** Refactor `SessionOrchestrator.resume` (or its caller in `session_cli_handlers.py`) to loop the `plan -> execute -> resume` cycle until the user explicitly cancels or an error occurs.

### Scenario: Planning Visibility & Turn Info [ ]
- **Given** the AI is generating a plan.
- **When** the LLM call is initiated.
- **Then** the CLI MUST immediately display a progress message.
- **And** the message MUST include the current Turn ID (e.g., `[02] Planning Turn with pathfinder...`).

#### Deliverables
- [ ] **Log Refactoring:** In `SessionOrchestrator._trigger_new_plan`, move the `display_message` call to *before* the `generate_plan` call. Use the folder name of `turn_dir` to extract the Turn ID.

### Scenario: Relaxed Terminal Action Isolation [ ]
- **Given** a plan contains a `PROMPT`, `INVOKE`, or `RETURN` action mixed with other actions.
- **When** the plan is reviewed in the TUI.
- **Then** the terminal action MUST NOT be hard-blocked.
- **And** the terminal action MUST be deselected (`[ ]`) by default in the TUI.
- **And** the user MUST be able to manually select it if they wish to override isolation.

#### Deliverables
- [ ] **Isolation Policy Update:** Update `ActionExecutor._check_action_isolation` to allow non-isolated terminal actions.
- [ ] **Default Selection Logic:** Update `MarkdownPlanParser` or `ActionExecutor` to set `selected=False` for `PROMPT`, `INVOKE`, and `RETURN` actions if `total_actions > 1`.

### Scenario: Telemetry Coloring Fix [ ]
- **Given** the telemetry (token count, cost) is displayed.
- **When** the values contain decimals or symbols (e.g., `32.5k`, `$0.04`).
- **Then** the entire value (including symbols and units) MUST be colored consistently.

#### Deliverables
- [ ] **Style Fix:** In `SessionOrchestrator._trigger_new_plan`, wrap the entire formatted strings for Model, Context, and Cost in the Rich style tags (e.g., `[cyan]Model: {model}[/]`).

## 3. Architectural Changes
- **IPlanReviewer Wiring:** Transitioning from a null-implementation to a live TUI-based implementation.
- **Stateful Loop:** Changing the session orchestrator from a one-shot execution to a continuous loop.
