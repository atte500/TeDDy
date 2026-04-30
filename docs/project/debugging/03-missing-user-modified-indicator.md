# Bug: Missing "User Modified" indicators in Execution Report

- **Status:** Unresolved
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)

## Symptoms
When a user modifies action parameters (e.g., the content of a CREATE action or the FIND/REPLACE blocks of an EDIT action) during the interactive approval phase, the final Execution Report does not display the expected `(user modified: field)` indicator in the Action Log header.

## Context & Scope
### Regressing Delta
The feature was intended to be implemented in slice `00-01-user-modified-audit-trail.md`. It appears the template logic is present, but the data populating `ActionLog.modified_fields` is incomplete or failing to track specific fields.

### Environmental Triggers
Reproducible in interactive mode (`teddy execute`) when modifying actions.

### Ruled Out
- `execution_report.md.j2`: Template already contains logic for `modified_fields`.

## Diagnostic Analysis
### Causal Model
1. User runs `teddy execute`.
2. `ExecutionOrchestrator` iterates through actions.
3. For each action, it prompts for approval/modification via `IUserInteractor` or `IPlanReviewer`.
4. If modified, the `Action` object is updated.
5. The `ActionDispatcher` (or Orchestrator) executes the action and returns an `ActionLog`.
6. The `ActionLog` SHOULD contain a list of `modified_fields` by comparing the original action state with the state at execution time.
7. `MarkdownReportFormatter` renders the report based on these logs.

### Discrepancies
- Report missing indicators. Conflict: Template has the code, but logs likely lack the data. (Resolved: ActionDispatcher, ActionExecutor, and ActionDiffManager fail to copy `modified_fields` from ActionData to ActionLog.)

### Investigation History
1. `git grep` confirmed template support and revealed existence of implementation slice.
2. Code audit of `ActionDispatcher.py` and `ActionExecutor.py` confirmed `modified_fields` is ignored during `ActionLog` creation.
3. Created MRE `debug/repro_modified_fields.py` confirming the bug.
4. Patched `ActionDispatcher`, `ActionExecutor`, and `ActionDiffManager` to preserve `modified_fields`.
5. Verified fix with MRE and formal regression test `tests/suites/acceptance/test_modified_audit_trail.py`.
6. Repaired collateral damage in `tests/suites/acceptance/test_context_aware_editing.py` where expectations needed to be updated to the more granular reporting format.

## Solution
### Implemented Fixes
- Updated `ActionDispatcher.dispatch_and_execute` to include `modified_fields` in the `ActionLog` metadata.
- Updated `ActionExecutor._create_intercepted_log` and `_enrich_failed_log` to propagate `modified_fields`.
- Updated `ActionDiffManager.inject_diff` and `_clean_log` to ensure the metadata is preserved when diffs are injected or removed.

### Prevention
- Added end-to-end regression test `tests/suites/acceptance/test_modified_audit_trail.py` which mocks the review phase to inject modifications and asserts their presence in the final Markdown report.
