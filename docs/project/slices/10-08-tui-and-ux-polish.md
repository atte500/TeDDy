# Slice 10-08: TUI & UX Polish
- **Status:** Planned
- **Milestone:** [Milestone 09: Interactive Session Workflow & LLM Integration](/docs/project/milestones/10-interactive-session-and-config.md)
- **Specs:** [Interactive Session Workflow](/docs/project/specs/interactive-session-workflow.md)

## 1. Business Goal
To enable the interactive TUI for all execution modes and polish the session workflow to provide better visibility, a continuous conversational loop, and relaxed but safe action isolation.

## 2. Acceptance Criteria (Scenarios)

### Scenario: UI Mode Toggling (TUI vs. Console) [✓]
- **Given** the configuration `ui_mode: "console"` is set in `.teddy/config.yaml`.
- **When** I run a plan.
- **Then** the system MUST use a sequential `ConsolePlanReviewer` that executes each action immediately after approval.
- **Given** the flag `--tui` is passed via CLI.
- **When** I run a plan.
- **Then** the system MUST override the config and use the `TextualPlanReviewer`.

#### Deliverables
- [✓] **Contract:** Update `IPlanReviewer` port to include `review_action` (per-action sequential) and `review_plan` (bulk TUI) methods.
- [✓] **Implementation:** Implement `ConsolePlanReviewer.review_action` to handle sequential Y/N logic and immediate execution.
- [✓] **Implementation:** Implement `ConsolePlanReviewer.review_plan` to handle bulk summary approval in non-interactive sessions.
- [✓] **Core Refactoring:** Update `ExecutionOrchestrator` to delegate action confirmation entirely to the `IPlanReviewer` port.
- [✓] **Wiring:** Update `YamlConfigAdapter` to support `ui_mode` (default: `tui`).
- [✓] **Wiring:** Update `container.py` to register `IPlanReviewer` implementation based on active configuration.
- [✓] **Wiring:** Update `execute`, `start`, and `resume` in `__main__.py` to support `--tui / --console` flags.

### Scenario: PRUNE Behavior in Manual Mode [ ]
- **Given** I am running a manual CLI execution (e.g., `teddy execute plan.md`).
- **And** the plan contains a `PRUNE` action.
- **When** the execution starts.
- **Then** the `PRUNE` action MUST NOT be reviewed by the user.
- **And** the `PRUNE` action MUST be automatically marked as `SKIPPED` in the execution report.

#### Deliverables
- [ ] **Contract:** Add `is_session` property to `Plan` domain model.
- [ ] **Implementation:** Update `MarkdownPlanParser` to set `is_session=True` if the plan is within a `.teddy/sessions/` directory.
- [ ] **Implementation:** Update `ActionExecutor` to automatically skip `PRUNE` actions if `plan.is_session` is `False`.
- [ ] **Implementation:** Update `ReviewerApp` (TUI) to filter out `PRUNE` actions from the UI tree if `plan.is_session` is `False`.

### Scenario: Continuous Session Loop [ ]
- **Given** I am in an interactive session.
- **When** a plan execution completes.
- **Then** the CLI MUST NOT exit and MUST prompt for new instructions.

#### Deliverables
- [ ] **Implementation:** Refactor `session_cli_handlers.py` to loop the `plan -> execute -> resume` cycle in a `while` loop.

### Scenario: Planning Visibility & Turn Info [ ]
- **Given** the AI is generating a plan.
- **When** the LLM call is initiated.
- **Then** the CLI MUST display `[Turn ID] Planning Turn with [agent]...` BEFORE the call.

#### Deliverables
- [ ] **Implementation:** Update `SessionOrchestrator._trigger_new_plan` to extract Turn ID from the folder name and display progress message before `generate_plan`.

### Scenario: Relaxed Terminal Action Isolation [ ]
- **Given** a plan contains a terminal action (`PROMPT`, `INVOKE`, `RETURN`) mixed with other actions.
- **When** reviewed in the TUI.
- **Then** the terminal action MUST be deselected (`[ ]`) by default but selectable by the user.

#### Deliverables
- [ ] **Implementation:** Update `ActionExecutor._check_action_isolation` to allow terminal actions in mixed plans.
- [ ] **Implementation:** Update `MarkdownPlanParser` to set `is_selected=False` for terminal actions if `total_actions > 1`.

### Scenario: Telemetry Coloring Fix [ ]
- **Given** telemetry (token count, cost) is displayed.
- **When** values contain symbols (e.g., `$0.04`).
- **Then** the entire string MUST be colored consistently.

#### Deliverables
- [ ] **Implementation:** Update `SessionOrchestrator._trigger_new_plan` to wrap entire formatted telemetry strings in Rich style tags.

## 3. Architectural Changes
- **Reviewer Port Expansion:** Moving from binary confirmation to a structured review interface.
- **Stateful Loop:** Converting the session handler from one-shot to a continuous loop.

## 4. Implementation Notes
- **Core Orchestration:** Refactored `ExecutionOrchestrator` to decouple action confirmation from execution. It now delegates the per-action decision to `IPlanReviewer.review_action` during interactive sessions.
- **Legacy Compatibility:** Implemented a robust fallback in `ExecutionOrchestrator` that preserves legacy `ActionExecutor` interaction if no `IPlanReviewer` is registered in the DI container.
- **Component:** Created `ConsolePlanReviewer` in `src/teddy_executor/adapters/inbound/console_plan_reviewer.py` to implement both sequential (`review_action`) and bulk (`review_plan`) interaction logic.
- **Shared Logic:** Extracted `ChangeSet` generation and action prompt formatting into a new core service: `ActionChangeSetBuilder`.
- **Bulk Review:** Implemented `review_plan` which utilizes a new `echo_plan_summary` helper in `cli_helpers.py`.
- **Validation:** Added unit tests in `test_console_plan_reviewer.py` covering `CREATE`, `EDIT`, `RESEARCH`, and bulk approval.
- **Configuration:** Updated `config/config.yaml` template to include `ui_mode: "tui"`.
- **Contract Expansion:** Updated `IPlanReviewer` and `IUserInteractor` ports to support the new multi-tier review model.
- **CLI Wiring:** Implemented `_apply_ui_mode_override` in `__main__.py` to allow runtime switching via `--tui/--console` flags.
- **Telemetry Hardening:** Updated `PlanningService` and `SessionPlanner` to handle potentially mocked telemetry values safely.

### Architectural Feedback
- **[DEBT] Deduplication:** Refactored `ActionExecutor` to use `ActionChangeSetBuilder`, reducing the `jscpd` duplication score from 3.59% to 0.76%.
