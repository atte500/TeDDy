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
Then a deprecation warning is displayed in the terminal via IUserInteractor
And the final execution report (report.md) contains these warnings to inform the AI
```

## Edge Cases
- **Message with Other Actions**: If a plan contains a `MESSAGE` action AND other actions (e.g., `CREATE`), then the `MESSAGE` should be treated as a normal action requiring approval. *Note: The Parser already enforces mutual exclusivity at the Section level, but ActionFactory might still create them if legacy actions are used alongside ## Action Plan.*
- **Empty Message Content**: If the `## Message` section is empty or contains only whitespace, then a `PlanValidationError` must be raised, in order to prevent silent, contentless handoffs.

## Deliverables
- [x] **Contract** - Add `notify_warning(message: str)` to `IUserInteractor` and `ConsoleInteractor`.
- [x] **Contract** - Update `ExecutionReport` domain model and `IExecutionReportAssembler` to support a `warnings` list.
- [ ] **Logic** - Implement `Plan.is_communication_turn()` and `ActionData.is_legacy` helpers.
- [ ] **Logic** - Implement validation in `PlanValidator` to reject `MESSAGE` actions with empty content.
- [ ] **Logic** - Update `ExecutionOrchestrator` to detect single-action `MESSAGE` plans and bypass the `IPlanReviewer` (TUI).
- [ ] **Logic** - Update `ExecutionOrchestrator` to display and record deprecation warnings for `PROMPT`, `INVOKE`, and `RETURN`.
- [ ] **Logic** - Update `MarkdownReportFormatter` to render the warnings section in the report.
- [ ] **Harness** - Add acceptance tests in `tests/suites/acceptance/test_message_protocol_orchestration.py`.
- [ ] **Refactor** - [DEBT] Refactor `ExecutionReportAssembler.assemble` parameters into a DTO to comply with `PLR0913` (too many arguments).

## Implementation Plan
1. Update `ExecutionReport` domain model to include a `warnings` list.
2. Modify `ExecutionOrchestrator` to check `plan.is_communication_turn()` (new helper in `Plan` model).
3. If true, call `user_interactor.display_message()` and proceed directly to report generation.
4. Add a check in the action execution loop to append warnings to the report if legacy types are encountered.
5. Update `MarkdownReportFormatter` to render the warnings section.

## Implementation Notes
### Deliverable: Contract - notify_warning
- Added `notify_warning(message: str)` to `IUserInteractor` interface to support deprecation warnings.
- Implemented `notify_warning` in `ConsoleInteractorAdapter` using Rich's `[bold yellow]WARNING:[/]`.
- Verified behavior with integration test `test_notify_warning_prints_formatted_message`.

### Deliverable: Contract - ExecutionReport Warnings
- Added `warnings: Sequence[str]` field to `ExecutionReport` domain model with `field(default_factory=list)` for backward compatibility.
- Updated `IExecutionReportAssembler` port and `ExecutionReportAssembler` service to support an optional `warnings` argument in the `assemble` method.
- Verified with unit tests for both the domain model and the assembler service.
- Confirmed global integration with a full test suite run.
