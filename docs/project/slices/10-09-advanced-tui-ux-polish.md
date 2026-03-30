# Slice 10-09: Advanced TUI & UX Polish
- **Status:** Planned
- **Milestone:** [Milestone 10: Interactive Session Workflow & LLM Integration](/docs/project/milestones/10-interactive-session-and-config.md)

## 1. Business Goal
To refine the interactive session workflow into a seamless, high-visibility experience by enabling instruction capture within the TUI, standardizing human-readable artifacts, and hardening diagnostic output.

## 2. Scenarios

### Scenario: Timestamped Context (Standard) [✓]
> As a developer, I want to see the exact time and date context was gathered so that I can audit and reproduce AI sessions with precision.

- **Given** `teddy context` is executed.
- **When** the project context is gathered.
- **Then** the Header MUST include `Current Date` and `Current Time`.

#### Deliverables
- [✓] **Logic** - Update `ContextService._format_header` to include current system time/date.

### Scenario: Soft Isolation for Terminal Actions (Non-TUI) [✓]
> As a developer using the non-interactive CLI, I want the system to automatically prevent the execution of terminal actions when they are part of a larger plan so that the AI receives feedback from other actions before making a state-changing decision.

- **Given** I run `teddy execute` (with or without `-y`) AND NOT using the TUI.
- **When** a plan contains a Terminal Action (`PROMPT`, `INVOKE`, `RETURN`).
- **And** the total number of actions in the plan is GREATER THAN 1.
- **Then** that Terminal Action MUST be automatically skipped.
- **And** the skip reason MUST be: "Action skipped to ensure state isolation; must be executed as a single-action plan."
- **Note:** If the Terminal Action is the ONLY action in the plan, it should execute normally (respecting `-y`).

#### Deliverables
- [✓] **Contract** - Add `is_terminal` property to `ActionData` model.
- [✓] **Logic** - Update `ActionExecutor.confirm_and_dispatch` to implement the soft isolation check.

### Scenario: Standardized Planning Artifact (`input.md`) [✓]
> As a developer, I want the AI's input to be a standardized, human-readable Markdown file (`input.md`) so that I can easily inspect and audit the exact context provided for each planning turn.

- **Given** a planning turn is initiated in an interactive session.
- **When** the input is saved to disk.
- **Then** it MUST be named `input.md` (instead of `input.log`).
- **And** it MUST contain the standard Project Context (Header, Git Status, Structure, Resource Contents).
- **And** the **Transition Algorithm** MUST ensure that both `plan.md` and `report.md` from the previous turn are added to the current `turn.context` (regardless of validation success/failure).

#### Deliverables
- [✓] **Logic** - Update `PlanningService.generate_plan` to write `input.md` using the standardized `ContextService` output.
- [✓] **Logic** - Update `SessionService.transition_to_next_turn` to always append BOTH the current turn's `plan.md` and `report.md` to the next turn's context.

### Scenario: Unified Instruction Bridge [✓] Verified
> As a user, I want a consistent way to provide instructions to the AI via a message flag or an in-TUI editor so that my requests are captured, documented, and passed between turns seamlessly.

- **Given** I am executing a session command (`start`, `resume`, or `execute`).
- **When** I provide a message via the `-m / --message` flag in `--console` mode.
- **Then** that message MUST be captured as the `user_request`.
- **And** the legacy interactive `typer.prompt` MUST be bypassed if a message is provided.
- **And** the TUI MUST provide an `m` binding ("Add Message") which opens an external editor to capture instructions.
- **And** these instructions MUST be stored in `plan.metadata["user_request"]` for the current execution.
- **And** these instructions MUST be appended to the final `Execution Report` (stdout/clipboard) or `report.md` under a `## User Request` section.
- **And** the **Transition Algorithm** MUST ensure this message is passed to the **next** turn's planning phase.

#### Deliverables
- [✓] **Contract** - Update `ExecutionReport` domain model and Jinja2 template to include the captured `user_request`.
- [✓] **Harness** - Update `CliTestAdapter` to allow mocking of external editor output for instruction capture.
- [✓] **Logic** - Update `SessionOrchestrator` to bridge instructions from CLI flags/reports to the planner.
- [✓] **Wiring** - Add `-m / --message` flag to `start`, `resume`, and `execute` commands in `__main__.py`.
- [✓] **Wiring** - Update `SessionCLIHandlers` to pass the message to the orchestrator.
- [✓] **Wiring** - Implement global `m` binding in `ReviewerApp` using the configured external editor.
- [✓] **Cleanup** - Remove legacy `typer.prompt` from session loops and handlers.

### Scenario: Message Consumption (Session & Manual) [✓] Verified
> As an AI agent, I want a clear, prioritized system for consuming user instructions so that I always act on the most recent and relevant request.

- **Given** a planning turn is initiated via `teddy plan` or as part of a session.
- **When** it looks for user instructions.
- **Then** it MUST check in this priority order:
  1. Explicit `message` passed from the current command (e.g., `resume -m "..."`).
  2. `user_request` found in the **previous** turn's `report.md` (for sessions) or a `report.md` in the CWD (for manual).
  3. Fallback: If in `--interactive` mode, prompt the user. If in `--no-interactive` mode, provide none and User Request section is not shown in execution report.

#### Deliverables
- [✓] **Logic** - Update `SessionPlanner` and `PlanningService` to implement the tiered message resolution logic.
- [✓] **Wiring** - Update `plan` command to make `-m` optional (defaulting to None).

### Scenario: TUI "View Plan" Workflow [✓] Verified
> As a user reviewing a plan in the TUI, I want to quickly open the full plan in my preferred editor so that I can get a complete, syntax-highlighted overview before approving it.

- **Given** I am in the `ReviewerApp` (TUI).
- **When** I press `v`.
- **Then** the entire `plan.md` currently being executed MUST open in the configured external editor.

#### Deliverables
- [✓] **Logic** - Update `ExecutionOrchestrator` to persist manual plan content to a temporary file to support the `v` binding in manual mode.
- [✓] **Wiring** - Add `v` binding to `ReviewerApp` to open the full plan content in the external editor.

### Scenario: Universal PROMPT Auto-Execution [✓] Verified
> As a user, I want single-action `PROMPT` plans to display their message immediately without needing approval so that I can have a more fluid, conversational interaction for simple checkpoints.

- **Given** a plan contains exactly ONE action of type `PROMPT`.
- **When** the execution starts.
- **Then** the `PROMPT` message MUST be displayed immediately without requiring user approval, regardless of session mode.

#### Deliverables
- [✓] **Logic** - Update `ExecutionOrchestrator._process_plan_actions` to automatically approve `PROMPT` actions if they are the sole action in any plan.

### Scenario: Context-Aware Editing (p key) [ ]
> As a user reviewing a plan in the TUI, I want to press a single key to preview and interactively edit any action so that I can make precise, fine-grained adjustments before execution.

- **Given** I am in the `ReviewerApp` (TUI).
- **When** I highlight an action and press `p`.
- **Then** it MUST trigger the specific workflow for that action type:
  - **CREATE**: Open content in editor; prompt for path in TUI; confirm save before applying.
  - **EDIT**: Simulate proposed final version; open in editor; confirm save; calculate final diff for the report.
  - **Simple (EXECUTE/RESEARCH)**: Modal view of content with an "Edit" option for text adjustment.
  - **Read-only (READ/PRUNE)**: Modal preview of the target resource.

#### Deliverables
- [ ] **Contract** - Ensure `report.md` explicitly notes when an action was `*modified` by the user.
- [ ] **Harness** - Update `ReviewerApp` driver in test harness to support simulated keypresses for modal editing.
- [ ] **Logic** - Implement "Proposed Final Version" simulation logic using `EditSimulator` in `ReviewerApp`.
- [ ] **Wiring** - Implement multi-stage `CREATE` workflow in `ReviewerApp`.
- [ ] **Wiring** - Implement multi-stage `EDIT` workflow in `ReviewerApp`.
- [ ] **Wiring** - Implement modal text editing for `EXECUTE` and `RESEARCH`.
- [ ] **Wiring** - Implement modal preview for `READ` and `PRUNE`.

### Scenario: Diagnostic Clarity (AST & Diffs) [ ]
> As a developer debugging a failed plan, I want validation errors to provide maximum clarity, including specific Markdown delimiters in the AST and standard diff headers, so that I can quickly diagnose and fix the root cause.

- **Given** a plan fails validation.
- **When** the AST view is displayed.
- **Then** Code Blocks MUST explicitly state the delimiter type and count (e.g., "Code Block (3 backticks)" or "Code Block (6 tildes)").
- **When** an `EDIT` match fails.
- **Then** the diff block MUST include standard headers: `--- Actual` and `+++ Provided`.

#### Deliverables
- [ ] **Logic** - Update `ParserReporting.format_node_name` to append precise delimiter metadata.
- [ ] **Logic** - Update `EditActionValidator._validate_single_edit` to include `--- Actual` and `+++ Provided` headers in the failure diff block.

## 3. Implementation Guidelines

### Test Harness Triad Strategy
- **Acceptance Layer:** Use `CliTestAdapter` and `MarkdownPlanBuilder` to verify the new TUI bindings (`m`, `v`, `p`) and terminal isolation logic.
- **Integration Layer:** Update `CliTestAdapter` to support TUI-specific interactions (like opening an external editor) via the `ReviewerApp` driver.
- **Unit Layer:** Use `pytest` parameterized tests for `ParserReporting` and `EditActionValidator` logic.

### Infrastructure & Artifacts
- **PlanningService:** Update `generate_plan` to write `input.md`. Use `self._context_service.get_context()` and the `format_project_context` helper from `cli_formatter.py`.
- **ContextService:** Update `_format_header` to include `datetime.now().isoformat()`.

### TUI & Loop
- **ReviewerApp:**
  - Add `BINDING` for `m` ("Add Message").
  - On trigger, suspend the TUI and open the configured external editor with a temporary file.
  - **Stateful Editing:** If instructions were already entered in the current TUI session, they MUST be loaded into the editor for refinement.
  - **Finalization:** The final content of the instruction buffer/file MUST only be moved to `self.plan.metadata["user_request"]` when the user presses `s` (Submit) to finalize the plan.
- **SessionPlanner:** Update `trigger_new_plan` to check for `user_request` in the *previous* turn's execution report or a temporary state file before prompting the user via the interactor.

### Orchestration & Validation
- **ExecutionOrchestrator:** In `_process_plan_actions`, if `len(plan.actions) == 1` and `action.type == "PROMPT"`, skip the `review_action` call and proceed to dispatch.
- **ParserReporting:** Update `format_node_name` to check `node.delimiter[0]` and append "(N tildes)" or "(N backticks)".
- **EditActionValidator:** Update `_validate_single_edit` to prepend `--- Actual\n+++ Provided\n` to the `diff_text`.

## 6. Implementation Notes
### Scenario: TUI "View Plan" Workflow
- **Plan Persistence:** Updated `ExecutionOrchestrator.execute` to persist manual plan content (when `plan_path` is missing) to a temporary file. This ensures that even plans provided via the clipboard have a physical file path that the TUI can open in an external editor using the `v` key. A `try...finally` block ensures the temporary file is deleted after execution.
- **Path Retention:** The `Plan` domain model was extended with a `plan_path` attribute, and the `MarkdownPlanParser` was updated to populate it. This preserves the file system location of the plan (whether permanent or temporary) across the application layers.
- **TUI Binding:** Implemented the `v` keybinding in `ReviewerApp`. It leverages the existing `_launch_editor` utility, which correctly handles TUI suspension and editor discovery (VISUAL/EDITOR/nano) while ensuring cross-platform compatibility.

### Scenario: Unified Instruction Bridge
- **Instruction Bridge Logic:** The `ExecutionOrchestrator` now bridges the `user_request` from plan metadata (populated by the CLI `-m` flag or the TUI `m` binding) to the final `ExecutionReport`.
- **TUI Suspension:** The `ReviewerApp` (TUI) uses the `suspend()` context manager to allow the user to edit messages in their preferred external editor without corrupting the terminal state.
- **Testability:** Added `TEDDY_TEST_MOCK_EDITOR_OUTPUT` check to `ReviewerApp._launch_editor` to allow automated acceptance tests to verify TUI editing logic.

### Standardized Planning Artifact (input.md)
- **Technical Decision:** Replaced the JSON-formatted `input.log` in `PlanningService` with a Markdown-formatted `input.md`. This file contains the project context (header + content) gathered by the `ContextService`.
- **Rational:** Standardizing the input as a Markdown artifact ensures it is human-readable on disk and consistent with the "Markdown as Interface" principle. It also simplifies context gathering for the planner.

### Timestamped Context Header
- **Technical Decision:** Extended the `IEnvironmentInspector` port and `SystemEnvironmentInspector` adapter to provide `current_date` and `current_time` rather than calculating them directly in `ContextService`. This maintains DI Purity and ensures the service remains testable with predictable mock values.
- **Formatting:** Used `strftime("%Y-%m-%d")` and `strftime("%H:%M:%S")` for consistency.

### Soft Isolation for Terminal Actions
- **Issue:** Multi-action plans containing `PROMPT`, `INVOKE`, or `RETURN` were being skipped in the TUI because the orchestrator passed `interactive=False` to the executor (to avoid double-prompting).
- **Fix:** Introduced a `skip_isolation` flag in `ActionExecutor.confirm_and_dispatch`. The orchestrator sets this to `True` when an `IPlanReviewer` (TUI) has already handled the action approval.
- **Refactoring:** Moved hardcoded terminal action detection in `ActionExecutor` to the `ActionData.is_terminal` domain property.

### Transition Logic
- `SessionService.transition_to_next_turn` now unconditionally appends the current turn's `plan.md` and `report.md` to the next turn's context. This ensures that even in self-correction loops triggered by validation failure, the AI has both its faulty plan and the specific error report in its worldview.
- **Path Resolution:** A private helper method `_to_root_relative` was introduced in `SessionService` to calculate correct project-root relative paths (e.g., `.teddy/sessions/name/01/plan.md`) to ensure the `ContextService` can reliably resolve and include them in the `input.md` artifact.

### Message Consumption (Tiered Resolution)
- **Priority Logic:** Implemented a tiered instruction resolution system in `PlanningService` and `SessionPlanner`. The order is: Command Line (`-m`) -> Previous `report.md` -> Interactive Prompt.
- **Shared Utilities:** Introduced `extract_markdown_section` in `markdown.py` to extract specific Markdown headers (like `## User Request`) for instruction consumption.
- **Alignment Hint:** Centralized the application of the "alignment hint" (`*(Stop to reply...)*`) in `PlanningService.generate_plan` to ensure all planning entry points consistently guide the LLM's behavior.

### Scenario: Universal PROMPT Auto-Execution
- **Auto-Approval Logic**: Implemented bypass for both the TUI (bulk review) and the sequential action review in `ExecutionOrchestrator` when a plan contains exactly one `PROMPT` action. This enables fluid, conversational interaction for simple status updates or questions.
- **Contract Alignment**: Synchronized the `IPlanReviewer` port and its `TextualPlanReviewer` implementation to ensure `agent_name` is correctly passed and handled, fixing a parameter name mismatch (`_agent_name` vs `agent_name`).
- **Test Harness Robustness**: Implemented a class-level `__init__` monkeypatch for the orchestrator in acceptance tests. This ensures mock injection even when services are resolved via protocols in complex CLI environments, providing a more reliable way to verify orchestration logic than standard container patching.
