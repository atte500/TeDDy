# Slice: 02-04-Context Automation

- **Status:** In Progress
- **Type:** Feature
- **Milestone:** [docs/project/milestones/02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [docs/project/specs/stability-and-bugfixes.md](/docs/project/specs/stability-and-bugfixes.md)

## Business Goal
Reduce manual friction in context management by automating path addition and relaxing validation rules that impede AI agent fluidity.

## Scenarios
> As a user, I want directories and URLs in my .context files to be correctly resolved so that I don't have to list every file manually.
```gherkin
Given a session context file containing:
  - "src/core/"
  - "https://example.com/spec.md"
When I run "teddy context"
Then the context should include all files inside "src/core/"
And it should include the remote URL "https://example.com/spec.md" as a resource
```

> As an AI agent, I want my successful file creations and edits to be automatically remembered in the next turn.
```gherkin
Given a plan with a successful "CREATE" of "new_file.py"
When the plan execution completes and transitions to the next turn
Then "new_file.py" should be present in the next turn's "turn.context"
```

## Edge Cases
- **Non-existent EDIT**: If I EDIT a file not in context that *does not exist*, validation should still fail (File Not Found), but NOT because of the context check.
- **Redundant EDIT**: If I provide a FIND/REPLACE pair where both are identical, it should be treated as a SUCCESS (no-op) and NOT a validation error.
- **Remote URL Deduplication**: URLs should be deduplicated against themselves but never treated as local paths.

## Deliverables
- [ ] **Contract** - Update `IFileSystemManager.resolve_paths_from_files` (if needed) to handle remote URLs.
- [ ] **Logic** - Update `ContextService._resolve_recursive` to explicitly handle `http/https` URLs.
- [ ] **Logic** - Update `EditActionValidator` to remove the context-presence check.
- [ ] **Logic** - Update `EditActionValidator` to treat identical FIND/REPLACE blocks as successful no-ops (suppressing the current error).
- [ ] **Logic** - Update `ReadActionValidator` to remove the "already in context" error.
- [ ] **Logic** - Update `SessionService._apply_execution_effects` to include `CREATE` and `EDIT` side-effects.
- [ ] **Harness** - Add integration test for recursive expansion of directories inside `.context` files.
- [ ] **Wiring** - Ensure `ExecutionReport` contains sufficient info for `SessionService` to verify file existence before auto-addition.

## Implementation Plan
### Delta Analysis
1.  **Relaxed Validation**:
    -   Modify `src/teddy_executor/core/services/validation_rules/edit.py`:
        -   Remove `if not is_path_in_context(path_str, context_paths):` block.
        -   In `_validate_single_edit`, if `find_block == replace_block`, return `[]` (empty errors) instead of a `ValidationError`.
    -   Modify `src/teddy_executor/core/services/validation_rules/filesystem.py`:
        -   In `ReadActionValidator`, remove the `is_path_in_context` check.
2.  **Context Automation**:
    -   Modify `src/teddy_executor/core/services/session_service.py`:
        -   Update `_apply_execution_effects` to iterate through `log.action_type` for `CREATE` and `EDIT`.
        -   For these types, resolve the path and verify existence via `self._repository.is_valid_path(path)` before adding to `paths`.
3.  **Recursive & URL support**:
    -   Modify `src/teddy_executor/core/services/context_service.py`:
        -   Update `_is_manifest` or `_resolve_recursive` to ensure URLs are not mistaken for local files and are preserved in the path list.
