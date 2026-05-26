# Slice: 01-02-Orchestrator Message Support

- **Status:** Planned
- **Milestone:** [docs/project/milestones/01-structural-message-protocol.md](/docs/project/milestones/01-structural-message-protocol.md)
- **Specs:** [docs/project/specs/handoff-protocol.md](/docs/project/specs/handoff-protocol.md)
- **Component Docs:** [docs/architecture/core/services/execution_orchestrator.md](/docs/architecture/core/services/execution_orchestrator.md)

## Business Goal
Enable the `ExecutionOrchestrator` to handle the new structural `MESSAGE` action, treating it as an auto-approving communication turn, while discouraging the use of legacy actions.

## Scenarios
> As a User, I want "Communication Turns" (messages only) to be presented to me directly without requiring a manual approval step, so that the conversation flows naturally.

```gherkin
Given a parsed plan containing only a "MESSAGE" action
When the orchestrator executes the plan
Then the message content is displayed to the user
And the user is NOT prompted for approval (Skip Approval Gate)
And the execution report confirms the message was delivered
```

> As a Developer, I want to be warned when I use legacy actions so that I am encouraged to migrate to the structural protocol.

```gherkin
Given a plan containing "PROMPT", "INVOKE", or "RETURN" actions
When the plan is executed
Then a deprecation warning is displayed in the terminal via IUserInteractor to alert the developer
And the final execution report (report.md) does NOT contain these warnings (to avoid AI confusion)
```

## Edge Cases
- **Message with Other Actions**: If a plan contains a `MESSAGE` action AND other actions (e.g., `CREATE`), then the `MESSAGE` should be treated as a normal action requiring approval. *Note: The Parser already enforces mutual exclusivity at the Section level, but ActionFactory might still create them if legacy actions are used alongside ## Action Plan.*
- **Empty Message Content**: If the `## Message` section is empty or contains only whitespace, then a `PlanValidationError` must be raised, in order to prevent silent, contentless handoffs.

## Deliverables
- [x] **Contract** - Add `notify_warning(message: str)` to `IUserInteractor` and `ConsoleInteractor`.
- [x] **Logic** - Implement `Plan.is_communication_turn()` and `ActionData.is_legacy` helpers.
- [x] **Logic** - Implement validation in `PlanValidator` to reject `MESSAGE` actions with empty content.
- [x] **Logic** - Update `ExecutionOrchestrator` to detect single-action `MESSAGE` plans and bypass the `IPlanReviewer` (TUI).
- [x] **Logic** - Update `ExecutionOrchestrator` to display terminal-only deprecation warnings for `PROMPT`, `INVOKE`, and `RETURN`.
- [ ] **Refactor** - [DEBT] Refactor `ExecutionOrchestrator` constructor to use a `Dependencies` DTO to reduce parameter count (currently 7).
- [ ] **Harness** - Add acceptance tests in `tests/suites/acceptance/test_message_protocol_orchestration.py`.
- [ ] **Refactor** - [DEBT] Refactor `ExecutionReportAssembler.assemble` parameters into a DTO to comply with `PLR0913` (too many arguments).

## Implementation Plan
1. Modify `ExecutionOrchestrator` to check `plan.is_communication_turn()` (new helper in `Plan` model).
2. If true, call `user_interactor.display_message()` and proceed directly to report generation.
3. Add a check in the action execution loop to trigger `user_interactor.notify_warning()` if legacy types are encountered.

## Implementation Notes
### Deliverable: Contract - notify_warning
- Added `notify_warning(message: str)` to `IUserInteractor` interface to support deprecation warnings.
- Implemented `notify_warning` in `ConsoleInteractorAdapter` using Rich's `[bold yellow]WARNING:[/]`.
- Verified behavior with integration test `test_notify_warning_prints_formatted_message`.

### Deliverable: Contract - ExecutionReport Warnings
- [DEPRECATED] Removed requirement for warnings in `ExecutionReport`. Warnings are now terminal-only to prevent AI confusion.

### Deliverable: Logic - Plan and ActionData Helpers
- Implemented `ActionData.is_legacy` property to identify `PROMPT`, `INVOKE`, and `RETURN` actions.
- Implemented `Plan.is_communication_turn()` to detect plans consisting of exactly one `MESSAGE` action.
- Added comprehensive unit tests in `tests/suites/unit/core/domain/models/test_plan_helpers.py`.

### Deliverable: Logic - Message Validation
- Created `MessageActionValidator` to enforce non-empty content for `MESSAGE` actions.
- Registered `MessageActionValidator` in `registries/validators.py`.
- Verified with unit tests in `tests/suites/unit/core/services/test_validator_message.py`.

### Deliverable: Logic - Orchestrate Deprecation Warnings
- Updated `ExecutionOrchestrator` to detect legacy actions (`PROMPT`, `INVOKE`, `RETURN`) during the execution loop.
- Injected `IUserInteractor` into the orchestrator to support real-time terminal warnings.
- Verified terminal output with unit and integration tests; ensured report remains clean.
