# Slice 00-05: Planning Lifecycle & UI Visibility

## Metadata
- **Status:** Planned
- **Milestone:** [Milestone 10: Interactive Session Workflow & LLM Integration](/docs/project/milestones/10-interactive-session-and-config.md)
- **Specs:** [Interactive Session Workflow](/docs/project/specs/interactive-session-workflow.md)
- **Prototypes:**
    - [Logic Prototype](/prototypes/slice_00_05_logic.py)
    - [Visual UX Prototype](/prototypes/final_session_ux_showcase.py)
    - [Telemetry Color Matrix](/prototypes/telemetry_color_matrix.py)
- **Component Docs:** [SessionService](/docs/architecture/core/services/session_service.md), [SessionOrchestrator](/docs/architecture/core/services/session_orchestrator.md), [SessionRepository](/docs/architecture/core/services/session_repository.md)

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
- [ ] **Contract** - Update `ISessionManager` and `IPlanningUseCase` definitions for session name resolution.
- [ ] **Harness** - Extend `CliTestAdapter` to capture `stderr` logs for planning visibility assertions.
- [ ] **Logic** - Implement chronological session sorting (date prefixing) in `SessionService`.
- [ ] **Logic** - Implement natural session name resolution in `SessionRepository`.
- [ ] **Logic** - Implement sequenced planning logs and "Proceed on Empty" in `PlanningService`.
- [ ] **Logic** - Implement telemetry color refinements in `SessionPlanner`.
- [ ] **Logic** - Implement terminal action soft isolation in `ExecutionOrchestrator`.
- [ ] **Wiring** - Resolve CLI infinite loops and consolidate planning logs in handlers.

## Delta Analysis

### Session Management (`SessionService` & `SessionRepository`)
- `SessionService.create_session`: Needs to inject `datetime.now().strftime("%Y%m%d_%H%M%S")` prefixing.
- `SessionService.rename_session`: Needs to regex-split the current name into `(prefix, name)` to preserve the prefix while updating the name slug.
- `SessionRepository.resolve_session_from_path`: Currently resolves the folder name directly. Needs to strip the `YYYYMMDD_HHMMSS-` prefix if present to return the natural session name for UI display.

### Planning Lifecycle (`PlanningService` & `SessionPlanner`)
- `PlanningService.generate_plan`:
    - Refactor to capture the session name (via `Path(turn_dir).parent.name`) and strip the prefix.
    - Centralize the `[cyan][{turn_id}] {session_name} | Waiting for {agent_name} to respond...` log here, immediately after the user message is resolved and before LLM invocation.
- `SessionPlanner._display_planning_telemetry`:
    - Update color styles: Bullets/Keys to `blue`, Values to `magenta`.
    - Replace `dim` with these specific colors for Model, Context, and Cost.

### Action Isolation (`ExecutionOrchestrator`)
- `ExecutionOrchestrator._handle_action_in_loop`:
    - Add logic to automatically skip terminal actions (PROMPT, INVOKE, RETURN) when `not interactive` and `len(plan.actions) > 1`.
    - Set skip reason to: `"Automatically skipped: This action must be performed in isolation."`

## Guidelines for Implementation

### 1. UI Style Guide (Colors & Styles)
- **Turn Header:** `[{turn_id}] {session_name} | Waiting for {agent} to respond...` MUST use **`cyan`**.
- **Telemetry Labels:** The bullet and key (e.g., `• Model:`) MUST use **`blue`**.
- **Telemetry Values:** The actual data (e.g., `gpt-4o`) MUST use **`magenta`**.
- **Instruction Prompt:** `Initial instructions for the session (type 'e' for editor)` MUST use **`bold white`**.

### 2. Logic & Sequencing
- **Prompt Frequency:** The manual instruction prompt MUST ONLY appear on **Turn 01**. Subsequent turns (Turn 02+) MUST proceed automatically using the context from the previous turn's execution report (User Request section).
- **Log Sequencing:** The `cyan` progress header MUST ONLY appear AFTER user instructions are captured (on Turn 1) or AFTER the lookback resolution (on Turn 2+).
- **Date Formatting:** Use `datetime.now().strftime("%Y%m%d_%H%M%S")` for session folder prefixes.
- **Prefix Handling:** `SessionService.rename_session` MUST preserve the existing `YYYYMMDD_HHMMSS-` prefix. Use `re.sub(r"^\d{8}_\d{6}-", "", old_name)` to get the slug and prepend the captured prefix to the new slug.

### 3. Terminal Action Isolation
- **Non-Interactive Mode:** If `interactive` is `False` (e.g., `execute -y`) and the plan contains multiple actions, terminal actions (`PROMPT`, `INVOKE`, `RETURN`) MUST be automatically skipped with the standard isolation reason: `"Automatically skipped: This action must be performed in isolation."`

### 3. Production vs. Prototype Mapping
The Developer MUST NOT implement simulation-only logs found in the prototype:
- **DO NOT** show "User input captured: ..." after a prompt.
- **DO NOT** show "Turn XX: Proceeding with context..." status messages.
- **DO** show the bulleted telemetry immediately after the LLM response is received.

## Session Resolution & Prefix Handling
- **Source of Truth:** `SessionRepository.resolve_session_from_path` MUST remain the source of truth for resolving folder names.
- **Prefix Stripping:** Use the regex `re.sub(r"^\d{8}_\d{6}-", "", folder_name)` for all UI display logic to ensure the "Natural Name" is shown while preserving the filesystem prefix.
- **Path Resolution:** All internal path builders MUST account for the `YYYYMMDD_HHMMSS-` prefix when looking for turn directories.

## Implementation Notes

### Deliverable: Infrastructure & Logic (Attempt 1 Findings)
- **Friction (Recursion):** Found that calling `resume` within `execute` (or vice-versa) in the CLI handlers leads to infinite recursion loops if state guards are not strictly defined.
- **Friction (Path Resolution):** Introduction of the date-time prefix caused regressions in `resolve_session_from_path` and `SessionService.get_latest_turn` because they relied on exact string matches for session names.
- **Friction (Log Sequencing):** The "Waiting for agent..." log was appearing before the user instruction prompt in Turn 1 due to the sequencing in `SessionOrchestrator`. It must be moved inside `PlanningService` to trigger only after the instruction is resolved.
- **Decision:** Shifted from a broad "Infrastructure" task to atomic DbC-prefixed deliverables to de-risk the async transformation and prefix implementation.
