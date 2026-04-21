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
- [x] Harness - Async infrastructure (Global `anyio_backend` fixture).
- [x] Harness - Async mock support in `mocks.py`.
- [x] Seam - Add `async_get_completion` to `ILlmClient` and implement in `LiteLLMAdapter`.
- [x] Seam - Add `async_generate_plan` to `IPlanningUseCase` and implement in `PlanningService`.
- [x] Seam - Add async counterparts to `ISessionManager` and `IRunPlanUseCase`.
- [x] Refactor - Progressively migrate `SessionOrchestrator` to async methods.
- [x] Logic - Chronological session sorting (date prefixing) in `SessionService`.
- [x] Logic - Natural session name resolution (prefix stripping) in `SessionRepository`.
- [x] Seam - Implement `ExecutionOrchestrator.async_execute` (wrapper around sync logic).
- [x] Seam - Implement async wrappers for `SessionReplanner` logic in `SessionOrchestrator`.
- [x] Logic - Sequenced planning logs & "Proceed on Empty" in `PlanningService.async_generate_plan`.
- [x] Logic - Blue/Magenta telemetry color refinements in `SessionPlanner`.
- [x] Logic - Terminal action soft isolation in `ExecutionOrchestrator.async_execute`.
- [x] Logic - Functional async wrappers for SessionService (ISessionManager).
- [ ] Harness - Unified Sync/Async mock bridging in TestEnvironment.
- [ ] Wiring - Async CLI integration (anyio runner) in session_cli_handlers.py.
- [ ] Cleanup - Prune recursion guards and synchronous methods in PlanningService.

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

### 0. Harness Repair: Mock Bridging
The systemic failure in integration tests revealed that existing mocks for synchronous ports (e.g., `ILlmClient.get_completion`) do not automatically apply to their async counterparts. We must update `UnifiedMock` in `test_environment.py` to synchronize `return_value` and `side_effect` between sync and async methods by default. This allows the SUT to transition to async calls without breaking the massive existing test suite.

### 1. Migration Strategy (Correction)
The initial attempt to convert ports to `async` in-place caused a systemic regression of 150+ test failures. We are pivoting to **Branch by Abstraction**:
1. Introduce async methods in parallel to existing sync methods in core ports.
2. Update implementations to support both.
3. Migrate high-level orchestrators turn-by-turn.
4. Prune sync paths once full coverage is achieved.

### 1. Hybrid Async Transformation
To support the TUI's stability requirements (native `push_screen_wait`) and non-blocking LLM calls, we are adopting a "Hybrid Async" model.
- **Core Services (Async):** `PlanningService`, `SessionOrchestrator`, and `ExecutionOrchestrator` will be migrated to `async def`. This allows the TUI to `await` the high-level orchestration turns.
- **Outbound Ports (Async):** `ILlmClient` (LiteLLM) and `IUserInteractor` (for TUI modals) will become async.
- **Synchronous Foundation:** `IFileSystemManager` and `IEnvironmentInspector` will **remain synchronous**. They are high-performance and low-risk. Services will bridge them using `anyio.to_thread.run_sync` when necessary to prevent blocking the event loop during heavy I/O.
- **CLI Adapters:** The `Typer` handlers in `session_cli_handlers.py` will be wrapped in `anyio.run` to drive the new async core.

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

### Deliverable: async_generate_plan Seam
- Introduced `async_generate_plan` to `IPlanningUseCase` and `PlanningService`.
- Implementation is a `NotImplementedError` to allow for incremental migration (Branch by Abstraction).
- Verified that adding the abstract method did not break existing DI or mocks in the test suite.

### Deliverable: Async counterparts for ISessionManager and IRunPlanUseCase
- Expanded `IRunPlanUseCase` (inbound) and `ISessionManager` (outbound) ports with `async_` prefixed methods.
- Implemented `NotImplementedError` stubs in `ExecutionOrchestrator`, `SessionOrchestrator`, and `SessionService`.
- Verified via `tests/suites/acceptance/test_async_port_migration.py` and global suite run.

### Deliverable: Refactor SessionOrchestrator Async Migration
- Migrated `SessionOrchestrator.async_execute` and `async_resume` to functional async implementations.
- Implemented `SessionPlanner.async_trigger_new_plan` to support async planning turns.
- Adopted "Hybrid Async" model: wrapping synchronous filesystem and service calls in `anyio.to_thread.run_sync` to prevent event loop blocking.
- Ratcheted acceptance test `test_run_plan_use_case_has_async_counterparts` to use a valid plan and session, pushing the failure frontier to the next unimplemented layer.
- Verified `SessionOrchestrator.async_execute` and `async_resume` correctly orchestrate the `async_generate_plan` and `async_execute` (stub) pipeline.
- Confirmed that the `MarkdownPlanParser` and `PlanningService` work correctly within the async event loop.

### Deliverable: Chronological Sorting & Natural Name Resolution
- Verified `SessionService.create_session` implements `YYYYMMDD_HHMMSS-` prefixing.
- Implemented `SessionRepository._strip_prefix` and updated `resolve_session_from_path` and `get_latest_session_name` to return Natural Names.
- Added unit tests in `tests/suites/unit/core/services/test_session_repository.py`.
- Verified via `tests/suites/acceptance/test_session_prefixing.py`.

### Deliverable: async_execute Seam
- Implemented `ExecutionOrchestrator.async_execute` using `anyio.to_thread.run_sync`.
- Verified that `SessionOrchestrator.async_resume` now correctly executes via the async thread wrapper.
- Ratcheted `tests/suites/acceptance/test_async_port_migration.py` to assert success for `IRunPlanUseCase` async methods.
