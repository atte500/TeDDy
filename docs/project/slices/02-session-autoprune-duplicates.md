# Slice: Session Auto-prune and Replan Persistence

- **Status:** Planned
- **Milestone:** [10-interactive-session-and-config](/docs/project/milestones/10-interactive-session-and-config.md)
- **Specs:** [interactive-session-workflow](/docs/project/specs/interactive-session-workflow.md), [context-management-ui](/docs/project/specs/context-management-ui.md)
- **Prototype:** N/A
- **Showcase:** N/A
- **Component Docs:** N/A

## Business Goal
Ensure that in interactive sessions, auto-pruned and manually-pruned files are correctly tracked, deduplicated to prevent double-counting, and reliably persisted to disk across standard execution and automated replan loops.

## Scenarios
> As a developer, I want to execute interactive plans with context thresholds so that context is cleanly pruned and correctly written to the next turn's files.

```gherkin
Scenario: Correct Deduplication and Pruning of Global Context
  Given a session with "session.context" and "turn.context" containing overlapping paths
  When the session orchestrator resolves and gathers project context
  Then each unique path must appear only once in the project context items
  And the global budget calculation must not double-count overlapping files

Scenario: Context Harvesting Persists Pruning in Interactive Mode
  Given an interactive session where some context files are pruned
  When the session orchestrator finishes executing the turn
  Then the pruned files must be harvested from the plan metadata
  And they must be correctly excluded from the next turn's "turn.context" on disk

Scenario: Replan Finalization Propagates Pruned Context
  Given an execution failure that triggers an automated replan
  When the session lifecycle manager triggers the replan loop
  Then the current plan must be propagated to the finalization logic
  And the pruned files must be correctly written to the next turn's manifest
```

## Edge Cases
- **Empty Manifests**: If `turn.context` or `session.context` is empty or missing, handling must degrade gracefully without raising exceptions.
- **System Prompts**: System prompts must never be included in pruning candidates or deselected during budget pruning.
- **Multiple Replans**: If multiple consecutive validation failures and replans occur, each turn must accurately chain the pruned context from the previous turn's metadata.

## Deliverables
- [ ] **Contract** - Add `plan: Optional[Plan] = None` to `ISessionLifecycleManager.trigger_replan` signature in the inbound/outbound ports.
- [ ] **Logic** - Refactor `ContextService._collect_items` to deduplicate collected `ContextItem` objects, ensuring only one item per unique path is registered, prioritizing non-`Turn` scopes if duplicates exist.
- [ ] **Logic** - Update `SessionLifecycleManager.trigger_replan` to accept and pass the `plan` parameter to `finalize_turn`.
- [ ] **Logic** - Update `SessionOrchestrator.execute` to pass the `plan` to `trigger_replan` when validation fails.
- [ ] **Logic** - Update `SessionOrchestrator` to harvest context in both interactive and non-interactive modes, ensuring pruned files are updated on disk.
- [ ] **Refactor** - Standardize test coverage to verify deduplication and persistence behavior.

## Implementation Notes
*Recorded during implementation.*

## Implementation Plan
1. **Deduplicate Context Items**: Implement deduplication loop in `src/teddy_executor/core/services/context_service.py` under `_collect_items` keeping unique paths only.
2. **Propagate Plan in Replan**: Edit `src/teddy_executor/core/services/session_lifecycle_manager.py` to add `plan` to `trigger_replan`, and edit `session_orchestrator.py` to pass the plan to `trigger_replan`.
3. **Harvest Interactive Context**: Update `SessionOrchestrator._harvest_context_if_non_interactive` (or rename it to `_harvest_context`) to run in both modes.
