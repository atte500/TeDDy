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
- [x] **Architecture Pivot: Synchronous Reversion**
  - [x] Cleanup - Remove all `async_` prefixed methods from core ports (`ILlmClient`, `IPlanningUseCase`, `IRunPlanUseCase`, `ISessionManager`).
  - [x] Cleanup - Revert `SessionOrchestrator`, `ExecutionOrchestrator`, and `PlanningService` strictly to synchronous `def` methods. Remove `anyio` dependencies.
  - [x] Cleanup - Remove `UnifiedMock` sync/async bridging and async mock support from `tests/harness/setup/mocking.py` and `test_environment.py`.
  - [x] Cleanup - Remove global `anyio_backend` fixtures from `conftest.py` and async marks from tests.
  - [x] Refactor - Ensure all tests rely on standard synchronous `MagicMock` for ports.
- [x] Logic - Chronological session sorting (date prefixing) in `SessionService`.
- [x] Logic - Natural session name resolution (prefix stripping) in `SessionRepository`.
- [x] Logic - Sequenced planning logs & "Proceed on Empty" in `PlanningService.generate_plan`.
- [x] Logic - Blue/Magenta telemetry color refinements in `SessionPlanner`.
- [x] Logic - Terminal action soft isolation in `ExecutionOrchestrator._handle_action_in_loop`.

## Implementation Notes

### Deliverable: Logic - Sequenced planning logs & "Proceed on Empty"
... (previous notes) ...

### Deliverable: Harness - Unified Sync/Async mock bridging
... (previous notes) ...

### Deliverable: Integration Failure & Pivot (2026-04-21)
- Attempted to wire CLI to async core using `anyio.run`.
- **Finding:** Systemic failure (17 tests) occurred because existing tests use standard `MagicMock` for `IRunPlanUseCase` and `IPlanningUseCase`.
- **Root Cause:** `anyio.run` hangs when attempting to await a non-awaitable `MagicMock`.
- **Decision:** Reverted code changes. Added a preliminary refactoring deliverable to ensure all test-registered mocks for primary ports are async-aware.

## Implementation Notes

### Deliverable: Logic - Sequenced planning logs & "Proceed on Empty"
- Implemented `async_generate_plan` in `PlanningService`.
- Added logic to substitute an empty user message with a default context-centric instruction.
- Sequenced the `[cyan]` progress log to appear after message resolution (Prompt/Lookback) but before context gathering/LLM call.
- Integrated prefix-stripping (Natural Name) resolution for session folders in the log message.

### Deliverable: Logic - Blue/Magenta Telemetry
- Refined `SessionPlanner._display_planning_telemetry` with new color scheme.
- Bullet and Key: `blue`.
- Value: `magenta`.
- Verified via unit tests in `test_session_planner.py`.

### Deliverable: Seam - SessionReplanner Async Wrappers
- Added `async_gather_failed_resources` and `async_trigger_replan_turn` to `SessionReplanner`.
- Updated `SessionOrchestrator` with `async_handle_logical_validation_errors` and `async_trigger_replan` to complete the async validation loop.

### Deliverable: Logic - Terminal Action Soft Isolation
- Verified that `ActionExecutor._check_action_isolation` already implements the soft isolation rule (skip if multi-action and non-interactive).
- Added unit test in `test_execution_orchestrator.py` to confirm the behavior.

## Delta Analysis

### 1. Architecture Pivot (Synchronous Reversion)
The initial attempt to migrate the core orchestration to an asynchronous architecture (`anyio`) caused systemic failures in the test harness (Bug 22) because the test suite fundamentally relies on synchronous `MagicMock` objects.
Upon architectural review, it was identified that the `Textual` TUI does not require a background event loop from the core application. It is only invoked during the plan review phase, where it manages its own blocking loop (`app.run()`). The LLM wait states are handled via standard synchronous `rich` console prints.
Therefore, the system MUST be reverted to a purely synchronous architecture. All `async_` prefixed methods, `anyio` dependencies, and complex mock bridging must be entirely stripped. This will permanently resolve Bug 22 and align the codebase with its synchronous test suite.

### 2. Session Management (`SessionService` & `SessionRepository`)
- **Sorting:** `SessionService.create_session` must inject `datetime.now().strftime("%Y%m%d_%H%M%S")` prefixing.
- **Renaming:** `SessionService.rename_session` must use regex to preserve the prefix while updating the name slug.
- **Resolution:** `SessionRepository.resolve_session_from_path` must strip the prefix to return the "Natural Name" for UI display, ensuring components like the Turn Header remain clean.

### 3. Planning Lifecycle (`PlanningService` & `SessionPlanner`)
- **Sequencing:** `PlanningService.generate_plan` is the new home for the `[cyan]` progress log. It must trigger *after* user instructions are resolved but *before* LLM invocation.
- **Continuity:** Implement "Proceed on Empty" logic to ensure the AI continues planning based on context if the user provides a null response.
- **Telemetry:** `SessionPlanner` telemetry styles must move from `dim` to `blue` (bullets/keys) and `magenta` (values) for higher visibility.

### 4. Action Isolation (`ExecutionOrchestrator`)
- **Soft Isolation:** Update `_handle_action_in_loop` to automatically skip terminal actions (`PROMPT`, `INVOKE`, `RETURN`) in non-interactive, multi-action plans.
- **Reasoning:** Ensure the skip reason clearly states: `"Automatically skipped: This action must be performed in isolation."`

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

### Technical Debt
- [ ] **File Length:** Refactor `src/teddy_executor/core/services/session_service.py` to meet 300-line limit (currently 343 lines).
- [ ] **Static Analysis:** Configure `.vulture_whitelist` to silence Protocol false positives in `ISessionManager`.
- [ ] **Typing:** Resolve pre-existing `bytes` vs `str` Mypy errors in `shell_adapter.py`.

### Deliverable: Infrastructure & Logic (Attempt 1 Findings)
- **Friction (Recursion):** Found that calling `resume` within `execute` (or vice-versa) in the CLI handlers leads to infinite recursion loops if state guards are not strictly defined.
- **Friction (Path Resolution):** Introduction of the date-time prefix caused regressions in `resolve_session_from_path` and `SessionService.get_latest_turn` because they relied on exact string matches for session names.
- **Friction (Log Sequencing):** The "Waiting for agent..." log was appearing before the user instruction prompt in Turn 1 due to the sequencing in `SessionOrchestrator`. It must be moved inside `PlanningService` to trigger only after the instruction is resolved.
- **Decision:** Shifted from a broad "Infrastructure" task to atomic DbC-prefixed deliverables to de-risk the async transformation and prefix implementation.

### Deliverable: Architecture Pivot (Sync Reversion)
- **Friction:** Introduction of `anyio.run` and `async` ports caused infinite loops, `TypeError` exceptions, and 120+ failing tests due to mismatched mock types, leading directly to Bug 22.
- **Resolution:** The async migration is officially aborted. The immediate next step is to revert all async-related additions across the ports, services, and test harness, returning the system to a clean, synchronous state.

### Deliverable: Chronological Sorting & Natural Name Resolution
- Verified `SessionService.create_session` implements `YYYYMMDD_HHMMSS-` prefixing.
- Implemented `SessionRepository._strip_prefix` and updated `resolve_session_from_path` and `get_latest_session_name` to return Natural Names.
- Added unit tests in `tests/suites/unit/core/services/test_session_repository.py`.
- Verified via `tests/suites/acceptance/test_session_prefixing.py`.

### Deliverable: Architecture Pivot (Synchronous Reversion)
- Reverted all core ports (`ILlmClient`, `IPlanningUseCase`, `IRunPlanUseCase`, `IPromptManager`) to strictly synchronous methods.
- Removed `UnifiedMock` from the test harness, transitioning to `POSIXPathMock` via `register_mock`.
- Cleaned up `anyio` dependencies and `async` logic from core services.
- Verified that TUI unit tests must remain `async def` to utilize the `Textual` `pilot` driver, but now interact correctly with the synchronous core.
- Fixed `AttributeError` and `ImportError` regressions in the test harness caused by residual async setups.
- Verified system integrity with a successful global test run (627 passed).
