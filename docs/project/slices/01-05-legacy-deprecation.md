# Slice: 01-05-Legacy Deprecation

- **Status:** Planned
- **Milestone:** [docs/project/milestones/01-structural-message-protocol.md](/docs/project/milestones/01-structural-message-protocol.md)
- **Specs:** [docs/project/specs/handoff-protocol.md](/docs/project/specs/handoff-protocol.md)

## Business Goal
Finalize the transition by removing all code-level support for `PROMPT`, `INVOKE`, `RETURN`, and `PRUNE`.

## Deliverables
- [ ] **Contract** - Remove `PROMPT`, `INVOKE`, `RETURN`, and `PRUNE` from `ActionType` enum in `src/teddy_executor/core/domain/models/plan.py`.
- [ ] **Logic** - Purge `is_legacy` and update `is_terminal` to only include `MESSAGE`.
- [ ] **Cleanup** - Remove parser strategies for legacy actions from `MarkdownPlanParser` and `action_parser_complex.py`.
- [ ] **Cleanup** - Remove legacy handling and `notify_warning` from `ActionExecutor` and `ExecutionOrchestrator`.
- [ ] **Cleanup** - Remove `PRUNE` side-effect logic from `SessionService`.
- [ ] **Cleanup** - Purge legacy-specific logic from `ExecutionReportAssembler` and `execution_report.md.j2` template.
- [ ] **Cleanup** - Strip legacy-specific preview, editor, and labeling logic from Textual TUI adapters (`src/teddy_executor/adapters/inbound/textual_plan_reviewer_*`).
- [ ] **Wiring** - Update `ActionFactory` to remove legacy mappings.
- [ ] **Harness** - Purge all legacy-specific tests in `tests/suites/unit/core/services/` and `tests/suites/acceptance/`.
