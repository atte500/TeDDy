# Slice: File Length Debt Reconciliation
- **Status:** Planned
- **Milestone:** [09-architectural-debt-reconciliation](../milestones/09-architectural-debt-reconciliation.md)
- **Component Docs:**
    - [SessionOrchestrator](../../architecture/core/services/session_orchestrator.md)
    - [ShellAdapter](../../architecture/outbound/shell_adapter.md)
    - [ExecutionOrchestrator](../../architecture/core/services/execution_orchestrator.md)
    - [PlanningService](../../architecture/core/services/planning_service.md)

## Business Goal
Satisfy project quality gates by decomposing oversized files into focused, smaller modules, improving maintainability and reducing cognitive load for developers and AI agents.

## Scenarios

### Scenario 1: SessionOrchestrator Decomposition
> As a Developer, I want SessionOrchestrator to be under 300 lines so that it is easier to understand and maintain.
```gherkin
Given a "SessionOrchestrator" with 487 lines
When I extract specialized logic (e.g., auto-naming, turn transition rules) into dedicated helper classes or services
Then "src/teddy_executor/core/services/session_orchestrator.py" MUST be <= 300 lines
And the total line count of the extracted components MUST remain stable
And the full test suite MUST remain green
```

### Scenario 2: Adapter & Service Pruning
> As a Maintainer, I want ShellAdapter and ExecutionOrchestrator to respect the 300-line limit so that the codebase remains modular.
```gherkin
Given files "shell_adapter.py" and "execution_orchestrator.py" exceeding 300 lines
When I extract platform-specific logic or reporting logic into focused helpers
Then both files MUST be <= 300 lines
And the system MUST continue to function correctly on all OS matrices
```

## Deliverables
- [x] **Logic** - Extract turn transition and state management from `SessionOrchestrator` to `SessionLifecycleManager`.
- [x] **Cleanup** - Verify `SessionOrchestrator` passes the `file-length-python` quality gate (282 lines).
- [x] **Logic** - Extract OS-specific command preparation from `ShellAdapter` to `ShellCommandBuilder`.
- [x] **Logic** - Extract report assembly and status determination from `ExecutionOrchestrator` to `ExecutionReportAssembler`.
- [x] **Logic** - Extract prompt resolution and alignment logic from `PlanningService` to a `PromptManager` or internal helper.
- [x] **Cleanup** - Verify `ShellAdapter`, `ExecutionOrchestrator`, and `PlanningService` pass the `file-length-python` quality gate.
- [x] **Logic** - Extract session migration and path management logic from `SessionService` to `SessionRepository`.
- [x] **Logic** - Extract Markdown block parsing strategies from `MarkdownPlanParser` to a strategy registry or internal helpers.
- [ ] **Logic** - Extract TUI preview formatting from `textual_plan_reviewer_previews.py`.
- [ ] **Cleanup** - Final verification of `file-length-python` gate.

## Delta Analysis
- **SessionOrchestrator:** This is the most complex decomposition. It currently handles turn transitions, auto-naming, content fetching, and file persistence. These should be split using the **Strategy** or **Service** patterns.
- **ShellAdapter:** Currently handles both POSIX and Windows logic. Extracting the `prepare` phase into a builder will significantly reduce its footprint.
- **Regression Risk:** These are central orchestrators. Any extraction must maintain the existing Port signatures and DI wiring to ensure zero impact on consumers.

## Guidelines for Implementation
- Use **Extract Class** for stateful logic and **Extract Method** (moved to new utilities) for stateless logic.
- Ensure all new components are correctly registered in `container.py`.
- Maintain strictly private attributes for any new internal dependencies.

## Implementation Notes

### Deliverable: Extract ShellCommandBuilder from ShellAdapter
- Extracted `ShellCommandBuilder` to handle OS-specific command preparation (bash traps and Windows wrapping).
- `ShellAdapter` now receives the builder via constructor injection.
- Verified line count: `ShellAdapter.py` is now 263 lines.
- **Friction:** Broken subcutaneous tests in `test_shell_adapter_windows_logic.py` required migration to the new builder. This confirmed the benefit of isolating this logic as the tests no longer require `sys.platform` mocking.
- Global integration verified via full shell test suite.

### Deliverable: Extract SessionLifecycleManager from SessionOrchestrator
- Extracted `SessionLifecycleManager` to handle `resume`, `finalize_turn`, and `trigger_replan` logic.
- `SessionOrchestrator` now acts as a pure entry point, coordinating parsing, validation, and execution.
- Verified line count: `SessionOrchestrator.py` is now 286 lines (under the 300-line limit).
- All 645 tests passed, confirming zero functional regressions.
- Logged pre-existing debt in `PlanningService` regarding file length.

### Deliverable: Extract ExecutionReportAssembler from ExecutionOrchestrator
- Extracted `ExecutionReportAssembler` to handle `RunStatus` determination and `ExecutionReport` DTO construction.
- `ExecutionOrchestrator` now receives the assembler via constructor injection.
- Verified line count: `ExecutionOrchestrator.py` is now 295 lines (under the 300-line limit).
- All tests (unit, integration, and global) passed, confirming behavioral parity.
- Registered the new port `IExecutionReportAssembler` and service in `container.py`.
- Fixed 6 test regressions caused by the orchestrator's signature change.

### Deliverable: Extract PromptManager from PlanningService
- Extracted `PromptManager` (and `IPromptManager` port) to handle prompt resolution, agent metadata lookups, and telemetry logging.
- `PlanningService` now acts as a pure orchestrator of context and LLM flow.
- Verified line count: `PlanningService.py` is now 184 lines.
- Updated the test harness with a safe-by-default `mock_prompt_manager` fixture.
- Migrated 9 unit tests to verify orchestration with `PromptManager` instead of low-level side effects on adapters.
- Final global integration verified: 644 tests green.

### Deliverable: Extract SessionRepository from SessionService
- Extracted low-level filesystem and path management logic from `SessionService` into `SessionRepository`.
- Defined `ISessionRepository` outbound port to satisfy DI boundary rules.
- `SessionService` now depends on `ISessionRepository` via constructor injection.
- Verified line count: `SessionService.py` is now 269 lines (under the 300-line limit).
- Global integration verified: 644 tests green.

### Deliverable: Extract Markdown block parsing strategies from `MarkdownPlanParser`
- Extracted `validate_plan_structure` to `parser_reporting.py` and `parse_plan_metadata` to `parser_metadata.py`.
- Resolved a circular import between `infrastructure` and `reporting` by keeping the structural validator in the reporting module (which already depended on infrastructure).
- `MarkdownPlanParser` now coordinates top-level flow using these helpers.
- Verified line count: `MarkdownPlanParser.py` is now 243 lines (under the 300-line limit).
- Global integration verified: 644 tests green.
