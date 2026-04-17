# Slice 00-05: Planning Lifecycle & UI Visibility

## Metadata
- **Status:** Planned
- **Milestone:** [Milestone 10: Interactive Session Workflow & LLM Integration](/docs/project/milestones/10-interactive-session-and-config.md)
- **Specs:** [Interactive Session Workflow](/docs/project/specs/interactive-session-workflow.md)
- **Prototypes:**
    - [Logic Prototype](/prototypes/slice_00_05_logic.py)
    - [Visual UX Prototype](/prototypes/final_session_ux_showcase.py)
- **Component Docs:** [SessionService](/docs/architecture/core/services/session_service.md), [SessionOrchestrator](/docs/architecture/core/services/session_orchestrator.md)

## Business Goal
To refine the interactive planning lifecycle and improve visibility into system state, ensuring that logs reflect the actual sequence of user events and the TUI provides high-clarity context at a glance.

## Scenarios

### Scenario: Logical Log Sequencing
> As a user, I want to see the "Planning Turn" message only after I've provided my instructions so that the UI reflects the actual sequence of events.

```gherkin
Given I am in an interactive session
When a planning turn starts
Then the message "[01] Planning Turn with pathfinder..." MUST ONLY appear after the user_request has been resolved
```

### Scenario: Session Visibility & Natural Language
> As a user, I want to see the name of the current session in the turn header using natural language so the UI feels intuitive and context-aware.

```gherkin
Given I am in an interactive session named "fix-login-bug"
When a planning turn starts (after I provide instructions)
Then the message MUST be: "[01] fix-login-bug | Waiting for pathfinder to respond..."
And telemetry labels (Model, Context, Cost) MUST be rendered in "bright_black" for high visibility.
```

### Scenario: AI-Driven Continuity (Proceed on Empty)
> As a user, I want the AI to proceed with planning based on the execution report even if I don't provide explicit instructions.

```gherkin
Given I am in an interactive session
When I provide an empty/null instruction
Then the PlanningService MUST NOT exit the loop
And it MUST proceed to call the LLM using the current context as the primary instruction
```

### Scenario: Soft Isolation Reporting
> As a user, I want terminal actions to show a clear reason for being skipped in multi-action plans so that the AI understands the protocol constraints.

```gherkin
Given a plan contains multiple actions, including a PROMPT, INVOKE, or RETURN
When I execute the plan in non-interactive mode
Then the terminal actions MUST be automatically skipped
And the report.md Action Log MUST state: "Automatically skipped because action should be run in isolation"
```

### Scenario: Chronological Session Sorting
> As a user, I want session folders to be prefixed with the current date and time so they are naturally sorted on my filesystem.

```gherkin
Given the current date is 2026-04-17 and time is 12:00:00
When I start a new session named "refactor-auth"
Then the session directory MUST be named "20260417_120000-refactor-auth"
```

## Deliverables
- [ ] **Logic** - Update `SessionService.create_session` to prefix the session directory name with `YYYYMMDD_HHMMSS-`.
- [ ] **Logic** - Update `SessionService.rename_session` to preserve the prefix during folder moves.
- [ ] **Logic** - Update `SessionRepository.resolve_session_from_path` to handle prefixed folder names.
- [ ] **Logic** - Refactor `PlanningService.generate_plan` to capture and display the progress message `[{turn_id}] {session_name} | Waiting for {agent_name} to respond...` after input resolution.
- [ ] **Logic** - Update `PlanningService.generate_plan` to return a `CONTINUE` signal (non-None) on empty input to trigger planning with current context.
- [ ] **Logic** - Update `SessionPlanner._display_planning_telemetry` to use `bright_black` for labels.
- [ ] **Logic** - Update `ExecutionOrchestrator._handle_action_in_loop` to record the specific "isolation" skip reason for terminal actions in multi-step plans.
- [ ] **Wiring** - Remove progress display calls from `SessionOrchestrator` and `SessionPlanner` (now handled by `PlanningService`).

## Delta Analysis
The current implementation of `SessionService` uses a simple name for session directories. Adding a date-time prefix requires updating `create_session` and ensuring that session resolution (via `resolve_session_from_path`) correctly handles the prefix. The display logic for planning turns is currently fragmented between `SessionOrchestrator` and `SessionPlanner`, providing an opportunity for consolidation and refinement.

## UI Style Guide & Implementation Guidelines

### 1. Colors & Styles
- **Turn Header:** `[{turn_id}] {session_name} | Waiting for {agent} to respond...` MUST use **`cyan`**.
- **Telemetry Labels:** `• Model:`, `• Context:`, `• Session Cost:` MUST use **`bright_black`** (grey). Do not use `dim`.
- **Instruction Prompt:** `Initial instructions for the session (type 'e' for editor)` MUST use **`bold white`**.

### 2. Logic & Sequencing
- **Prompt Frequency:** The manual instruction prompt MUST ONLY appear on **Turn 01**. Subsequent turns (Turn 02+) MUST proceed automatically using the context from the previous turn's execution report (User Request section).
- **Log Sequencing:** The `cyan` progress header MUST ONLY appear AFTER user instructions are captured (on Turn 1) or AFTER the lookback resolution (on Turn 2+).
- **Date Formatting:** Use `datetime.now().strftime("%Y%m%d_%H%M%S")` for session folder prefixes.
- **Prefix Handling:** `SessionService.rename_session` MUST preserve the existing `YYYYMMDD_HHMMSS-` prefix when renaming.

### 3. Production vs. Prototype Mapping
The Developer MUST NOT implement simulation-only logs found in the prototype:
- **DO NOT** show "User input captured: ..." after a prompt.
- **DO NOT** show "Turn XX: Proceeding with context..." status messages.
- **DO** show the bulleted telemetry immediately after the LLM response is received.

## Session Resolution
- Ensure `SessionRepository.resolve_session_from_path` remains the source of truth for the folder name, accounting for the new prefix.

## Implementation Notes
(To be filled by Developer)
