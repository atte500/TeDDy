# Slice: 01-05-Legacy Deprecation

- **Status:** Planned
- **Milestone:** [docs/project/milestones/01-structural-message-protocol.md](/docs/project/milestones/01-structural-message-protocol.md)
- **Specs:** [docs/project/specs/handoff-protocol.md](/docs/project/specs/handoff-protocol.md)

## Business Goal
Finalize the transition by removing all code-level support for `PROMPT`, `INVOKE`, `RETURN`, and `PRUNE`.

## Deliverables
- [ ] **Cleanup** - Remove legacy types from `ActionType` enum.
- [ ] **Cleanup** - Remove `is_legacy` and `is_terminal` logic referencing legacy types.
- [ ] **Cleanup** - Remove dispatch and parser strategies from `MarkdownPlanParser`.
- [ ] **Cleanup** - Delete `action_parser_complex.py` legacy functions.
- [ ] **Cleanup** - Remove `LEGACY_DEPRECATION_WARNING` from `ExecutionOrchestrator`.
- [ ] **Wiring** - Ensure `is_communication_turn` only checks for `MESSAGE`.
- [ ] **Cleanup** - Global check to ensure all legacy references have been purged both in code as well as in docs.
