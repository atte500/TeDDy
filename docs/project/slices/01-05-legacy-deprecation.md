# Slice: 01-05-Legacy Deprecation

- **Status:** In Progress
- **Milestone:** [docs/project/milestones/01-structural-message-protocol.md](/docs/project/milestones/01-structural-message-protocol.md)
- **Specs:** [docs/project/specs/handoff-protocol.md](/docs/project/specs/handoff-protocol.md)

## Business Goal
Finalize the transition by removing all code-level support for `PROMPT`, `INVOKE`, `RETURN`, and `PRUNE`.

## Deliverables
- [x] **Contract** - Remove `PROMPT`, `INVOKE`, `RETURN`, and `PRUNE` from `ActionType` enum in `src/teddy_executor/core/domain/models/plan.py`.
- [x] **Logic** - Purge `is_legacy` and update `is_terminal` to only include `MESSAGE`.
- [▶] **Cleanup** - Purge `PROMPT` and `PRUNE` remnants from `ActionDispatcher` and `validation_rules/filesystem.py`.
- [x] **Cleanup** - Remove parser strategies for legacy actions from `MarkdownPlanParser` and `action_parser_complex.py`.
- [x] **Cleanup** - Remove legacy handling, `is_terminal` property, and `notify_warning` from `ActionExecutor` and `ExecutionOrchestrator`.
- [x] **Cleanup** - Remove `PRUNE` side-effect logic from `SessionService`.
- [x] **Cleanup** - Purge legacy-specific logic from `ExecutionReportAssembler` and `execution_report.md.j2` template.
- [x] **Cleanup** - Strip legacy-specific preview, editor, and labeling logic from Textual TUI adapters (`src/teddy_executor/adapters/inbound/textual_plan_reviewer_*`).
- [x] **Wiring** - Update `ActionFactory` to remove legacy mappings.
- [x] **Harness** - Purge all legacy-specific tests in `tests/suites/unit/core/services/` and `tests/suites/acceptance/`.
- [ ] **Cleanup** - Replace bare MagicMocks in `tests/suites/acceptance/helpers.py` and `tests/suites/unit/core/services/test_action_executor.py` with `register_mock`.

## Implementation Notes
- **Action Models**: Re-added `ActionData.is_terminal` (property) and `Plan.is_communication_turn` (method) to the domain model as they are essential for the `ExecutionOrchestrator` to identify `MESSAGE` turns and bypass approval/reviews for fluid conversation.
- **Protocol Shift**: Successfully removed `PROMPT`, `INVOKE`, `RETURN`, and `PRUNE` action types. All agent communication is now handled via the structural `## Message` section.
- **Test Purge**: Deleted several legacy unit and acceptance test files (`test_action_dispatcher.py`, `test_parser_edit_bulk.py`, etc.) that were dedicated to the removed actions.
- **Harness Stability**: Fixed signature mismatches in `ReportParser` and test assertions that were broken by the property/method transitions.
- **Audit Findings**: Discovered remaining `PROMPT` strings in `ActionDispatcher` and `PRUNE` logic in `validation_rules/filesystem.py`. Updated planning to include their removal and harvested `MagicMock` debt in tests.
