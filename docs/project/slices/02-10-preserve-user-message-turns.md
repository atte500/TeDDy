# Slice: 02-10-Preserve User-Message Turns
- **Status:** To De-risk
- **Type:** Feature
- **Milestone:** [docs/project/milestones/02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [docs/project/specs/stability-and-bugfixes.md](/docs/project/specs/stability-and-bugfixes.md)
- **Component Docs:** [docs/architecture/core/services/session_pruning_service.md](/docs/architecture/core/services/session_pruning_service.md)

## Business Goal
Protect action turns where the user provided an additional message during the review phase from being pruned by the automatic session pruning logic. This ensures user contributions are preserved in the session context for future turns.

## Scenarios
> As a user, I want action turns where I provided a message during review (via TUI 'm' key or reply) to be spared from auto-pruning, so that my instructions and context are not lost.
```gherkin
Given a session with auto-pruning enabled
And the active turn has a plan with actions (not a ## Message turn)
And the user provided an additional message during review
When the pruning service evaluates this turn
Then the turn should be spared from pruning
And its files should remain selected in the project context
```

> As a user, I want pure message turns (## Message plans) to continue being spared from auto-pruning, so that the existing behavior is preserved.
```gherkin
Given a session with auto-pruning enabled
And a turn has a plan containing a ## Message section (message turn)
And the report shows Overall Status: SUCCESS
When the pruning service evaluates this turn
Then the turn should be spared from pruning
And its files should remain selected in the project context
```

## Edge Cases
- **Missing Report File**: If a turn has a plan but no report.md (e.g., execution was aborted), the service should not crash and should not attempt to read a missing file.
- **Empty User Request**: If the user_request metadata line is present but empty, the turn should not be spared (empty message is not a meaningful contribution).
- **Concurrent User Request and User Message**: If a turn contains both a `## Message` plan and a `user_request` metadata entry, it should be spared (already covered by existing message turn sparing).
- **Multiple Pruning Heuristics**: A turn spared by this rule must be exempted from ALL pruning heuristics (retention limit, global budget, non-green recovery, validation failure) to be consistent with existing message turn sparing.

## Deliverables
- [ ] **Harness** - Unit tests for `_check_report_has_user_request` helper (positive: report with user_request; negative: report without; edge: missing file, empty value).
- [ ] **Harness** - Unit tests for spared turn integration (turns with user_request are not pruned by retention limit or global budget).
- [ ] **Logic** - Implement `_check_report_has_user_request(path: str) -> bool` in `SessionPruningService` to detect `- **User Request:**` pattern in report files.
- [ ] **Logic** - Extend `_update_turn_metadata_from_item` to collect turn IDs where the report has a user request and add them to the spared set.
- [ ] **Wiring** - Integration test verifying full pruning flow: session with user-request turn is not pruned.
- [ ] **Cleanup** - Rename `successful_messages` variable (and related parameter names) to `spared_turns` to reflect the broader sparing logic.

## Implementation Notes

### Turn 1: Exploration
- Read `SessionPruningService`, `ExecutionReport`, `SessionOrchestrator`, `ExecutionReportAssembler`, and specs.
- Current sparing logic only preserves turns with `## Message` plans (via `_check_plan_is_message` + `_check_report_is_success`).
- Gap: Action turns with `user_request` in report metadata are not spared.
- No port or domain model changes needed — only internal refactoring of `SessionPruningService`.

### Turn 2: Alignment
- Approved approach: Add `_check_report_has_user_request` check, extend `_update_turn_metadata_from_item` to collect user-request turn IDs, add them to spared set.
- Identified debt: `successful_messages` variable name is semantically misleading after this change; rename to `spared_turns` in cleanup.

## Implementation Plan
No new ports or domain models needed. All changes are confined to `SessionPruningService`:

1. Add `_check_report_has_user_request(self, path: str) -> bool` — reads report file, checks for `- **User Request:**` pattern.
2. In `_update_turn_metadata_from_item`, add a new metadata collection path: if the report has a user request, add the turn ID to the spared set (alongside existing message turn sparing).
3. Rename `successful_messages` to `spared_turns` everywhere (variable name, parameter name, docstrings).

```
flowchart TD
    A[SessionPruningService.prune] --> B[_identify_turns_to_prune]
    B --> C[_collect_turn_metadata]
    C --> D[_update_turn_metadata_from_item]
    D --> E{report has user_request?}
    E -->|Yes| F[Add turn ID to spared_turns set]
    E -->|No| G{plan is ## Message?}
    G -->|Yes + SUCCESS| F
    G -->|No| H[Continue normal pruning]
    F --> I[Exempt spared turns from all heuristics]
    I --> J[Return pruned context]
```
