# Slice 00-05: Planning Lifecycle & UI Visibility
- **Status:** Planned
- **Milestone:** [Milestone 10: Interactive Session Workflow & LLM Integration](/docs/project/milestones/10-interactive-session-and-config.md)

## 1. Business Goal
To refine the interactive planning lifecycle and improve visibility into system state, ensuring that logs reflect the actual sequence of user events and the TUI provides high-clarity context at a glance.

## 2. Scenarios

### Scenario: Logical Log Sequencing
> As a user, I want to see the "Planning Turn" message only after I've provided my instructions so that the UI reflects the actual sequence of events.

- **Given** I am in an interactive session.
- **When** a planning turn starts.
- **Then** the message `[01] Planning Turn with pathfinder...` MUST ONLY appear after the `user_request` has been resolved (either via CLI flag, lookback, or TUI input).

#### Deliverables
- [ ] **Logic** - Move the display of the progress message in `SessionPlanner.trigger_new_plan` to *after* the `PlanningService.generate_plan` call or within it, ensuring it follows instruction capture.

### Scenario: AI-Driven Continuity (Proceed on Empty)
> As a user, I want the AI to proceed with planning based on the execution report even if I don't provide explicit instructions.

- **Given** I am in an interactive session.
- **When** I provide an empty/null instruction.
- **Then** the `PlanningService` MUST NOT exit the loop.
- **And** it MUST proceed to call the LLM using the current context (including the `report.md` of the previous turn) as the primary instruction.

#### Deliverables
- [ ] **Logic** - Update `PlanningService.generate_plan` to treat empty input as a valid "Proceed with Context" signal.
- [ ] **Logic** - Ensure `SessionOrchestrator` does not interpret empty return values from planning as a "Cancel" signal unless explicitly triggered by a `q` (Quit) equivalent.

### Scenario: Soft Isolation Reporting
> As a user, I want terminal actions to show a clear reason for being skipped in multi-action plans so that the AI understands the protocol constraints.

- **Given** a plan contains multiple actions, including a `PROMPT`, `INVOKE`, or `RETURN`.
- **When** I execute the plan in `-y` mode (or non-interactive console mode).
- **Then** the terminal actions MUST be automatically skipped.
- **And** the `report.md` Action Log MUST state: "Automatically skipped because action should be run in isolation".

#### Deliverables
- [ ] **Logic** - Update `ExecutionOrchestrator` or `ExecutionReport` domain model to resolve a specific `skip_reason` for terminal actions in multi-action plans.
- [ ] **Logic** - Update `MarkdownReportFormatter` to render the specific "isolation" reason instead of the generic deselection message for terminal actions.

## 3. Implementation Guidelines

### Verification Strategy
- **Manual Verification:** Verify the TUI header and planning progress messages visually during a session.
- **Acceptance Tests:** Update `test_interactive_execution.py` or equivalent to verify that the planning service continues on empty input.
- **Unit Tests:** Verify the instruction template stripping logic in `TextualPlanReviewer`.
