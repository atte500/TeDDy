# Slice 10-09: Advanced TUI & UX Polish
- **Status:** Planned
- **Milestone:** [Milestone 10: Interactive Session Workflow & LLM Integration](/docs/project/milestones/10-interactive-session-and-config.md)

## 1. Business Goal
To refine the interactive session workflow into a seamless, high-visibility experience by enabling instruction capture within the TUI, standardizing human-readable artifacts, and hardening diagnostic output.

## 2. Acceptance Criteria (Scenarios)

### Scenario: Timestamped Context (Standard) [✓]
- **Given** `teddy context` is executed.
- **When** the project context is gathered.
- **Then** the Header MUST include `Current Date` and `Current Time`.

#### Deliverables
- [✓] **Implementation:** Update `ContextService._format_header` to include current system time/date.

### Scenario: Soft Isolation for Terminal Actions (Non-TUI) [ ]
- **Given** I run `teddy execute` (with or without `-y`) AND NOT using the TUI.
- **When** a plan contains a Terminal Action (`PROMPT`, `INVOKE`, `RETURN`).
- **And** the total number of actions in the plan is GREATER THAN 1.
- **Then** that Terminal Action MUST be automatically skipped.
- **And** the skip reason MUST be: "Terminal actions are skipped in bulk execution to ensure isolation; please execute them as a single-action plan."
- **Note:** If the Terminal Action is the ONLY action in the plan, it should execute normally (respecting `-y`).

#### Deliverables
- [✓] **Domain:** Add `is_terminal` property to `ActionData` model.
- [ ] **Implementation:** Update `ActionExecutor.confirm_and_dispatch` to implement the soft isolation check.
- [ ] **UX Polish:** Ensure `ExecutionOrchestrator` uses the descriptive reason "User deselected this action in the plan reviewer." ONLY when skipped via TUI.

### Scenario: Standardized Planning Artifact (`input.md`) [ ]
- **Given** a planning turn is initiated in an interactive session.
- **When** the input is saved to disk.
- **Then** it MUST be named `input.md` (instead of `input.log`).
- **And** it MUST contain the standard Project Context (Header, Git Status, Structure, Resource Contents).
- **And** the **Transition Algorithm** MUST ensure that both `plan.md` and `report.md` from the previous turn are added to the current `turn.context` (regardless of validation success/failure).

#### Deliverables
- [ ] **Implementation:** Update `PlanningService.generate_plan` to write `input.md` using the standardized `ContextService` output.
- [ ] **Implementation:** Update `SessionService.transition_to_next_turn` to always append BOTH the current turn's `plan.md` and `report.md` to the next turn's context.

### Scenario: Global TUI Instruction Bridge & Prompt Deprecation [ ]
- **Given** I am in the `ReviewerApp` (TUI), regardless of session mode.
- **When** the execution loop starts.
- **Then** the legacy CLI instruction prompt (typer.prompt) MUST be entirely removed.
- **And** the TUI MUST provide an `m` binding ("Add Message") which opens an external editor to capture instructions.
- **And** these instructions MUST be stored in `plan.metadata["next_instructions"]`.
- **And** these instructions MUST be appended to the final `Execution Report` (stdout/clipboard) or `report.md` under a `## User Request` section.

#### Deliverables
- [ ] **Implementation:** Remove legacy `typer.prompt` from session loops and handlers.
- [ ] **Implementation:** Implement global `m` binding in `ReviewerApp` using the configured external editor.
- [ ] **Implementation:** Update `ExecutionReport` domain model and Jinja2 template to include the captured `next_instructions` for manual workflow feedback.
- [ ] **Implementation:** Update `SessionOrchestrator` to bridge instructions back to the planner in session mode.

### Scenario: TUI "View Plan" Workflow [ ]
- **Given** I am in the `ReviewerApp` (TUI).
- **When** I press `v`.
- **Then** the entire `plan.md` currently being executed MUST open in the configured external editor.

#### Deliverables
- [ ] **Implementation:** Add `v` binding to `ReviewerApp` to open the full plan content in the external editor.
- [ ] **Technical Detail:** Use the existing `plan.md` file located in the turn directory for sessions.
- [ ] **Implementation:** Update `ExecutionOrchestrator` to persist manual plan content to a temporary file to support the `v` binding in manual mode.

### Scenario: Universal PROMPT Auto-Execution [ ]
- **Given** a plan contains exactly ONE action of type `PROMPT`.
- **When** the execution starts.
- **Then** the `PROMPT` message MUST be displayed immediately without requiring user approval, regardless of session mode.

#### Deliverables
- [ ] **Implementation:** Update `ExecutionOrchestrator._process_plan_actions` to automatically approve `PROMPT` actions if they are the sole action in any plan.

### Scenario: Context-Aware Editing (p key) [ ]
- **Given** I am in the `ReviewerApp` (TUI).
- **When** I highlight an action and press `p`.
- **Then** it MUST trigger the specific workflow for that action type:
  - **CREATE**: Open content in editor; prompt for path in TUI; confirm save before applying.
  - **EDIT**: Simulate proposed final version; open in editor; confirm save; calculate final diff for the report.
  - **Simple (EXECUTE/RESEARCH)**: Modal view of content with an "Edit" option for text adjustment.
  - **Read-only (READ/PRUNE)**: Modal preview of the target resource.

#### Deliverables
- [ ] **Implementation:** Implement multi-stage `CREATE` workflow in `ReviewerApp`.
- [ ] **Implementation:** Implement "Proposed Final Version" simulation logic using `EditSimulator` and multi-stage `EDIT` workflow in `ReviewerApp`.
- [ ] **Implementation:** Implement modal text editing for `EXECUTE` and `RESEARCH`.
- [ ] **Implementation:** Implement modal preview for `READ` and `PRUNE`.
- [ ] **Contract:** Ensure `report.md` explicitly notes when an action was `*modified` by the user.

### Scenario: Diagnostic Clarity (AST & Diffs) [ ]
- **Given** a plan fails validation.
- **When** the AST view is displayed.
- **Then** Code Blocks MUST explicitly state the delimiter type and count (e.g., "Code Block (3 backticks)" or "Code Block (6 tildes)").
- **When** an `EDIT` match fails.
- **Then** the diff block MUST include standard headers: `--- Actual` and `+++ Provided`.

#### Deliverables
- [ ] **Implementation:** Update `ParserReporting.format_node_name` to append precise delimiter metadata.
- [ ] **Implementation:** Update `EditActionValidator._validate_single_edit` to include `--- Actual` and `+++ Provided` headers in the failure diff block.

## 3. Implementation Guidelines

### Infrastructure & Artifacts
- **PlanningService:** Update `generate_plan` to write `input.md`. Use `self._context_service.get_context()` and the `format_project_context` helper from `cli_formatter.py`.
- **ContextService:** Update `_format_header` to include `datetime.now().isoformat()`.

### TUI & Loop
- **ReviewerApp:**
  - Add `BINDING` for `m` ("Add Message").
  - On trigger, suspend the TUI and open the configured external editor with a temporary file.
  - **Stateful Editing:** If instructions were already entered in the current TUI session, they MUST be loaded into the editor for refinement.
  - **Finalization:** The final content of the instruction buffer/file MUST only be moved to `self.plan.metadata["next_instructions"]` when the user presses `s` (Submit) to finalize the plan.
- **SessionPlanner:** Update `trigger_new_plan` to check for `next_instructions` in the *previous* turn's execution report or a temporary state file before prompting the user via the interactor.

### Orchestration & Validation
- **ExecutionOrchestrator:** In `_process_plan_actions`, if `len(plan.actions) == 1` and `action.type == "PROMPT"`, skip the `review_action` call and proceed to dispatch.
- **ParserReporting:** Update `format_node_name` to check `node.delimiter[0]` and append "(N tildes)" or "(N backticks)".
- **EditActionValidator:** Update `_validate_single_edit` to prepend `--- Actual\n+++ Provided\n` to the `diff_text`.

## 6. Implementation Notes
### Timestamped Context Header
- **Technical Decision:** Extended the `IEnvironmentInspector` port and `SystemEnvironmentInspector` adapter to provide `current_date` and `current_time` rather than calculating them directly in `ContextService`. This maintains DI Purity and ensures the service remains testable with predictable mock values.
- **Formatting:** Used `strftime("%Y-%m-%d")` and `strftime("%H:%M:%S")` for consistency.
