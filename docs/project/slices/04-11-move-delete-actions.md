# Slice: MOVE and DELETE Actions with Manifest Sync
- **Status:** Planned
- **Milestone:** [Milestone 4: TUI & UX Enhancements](/docs/project/milestones/04-tui-ux-enhancements.md)
- **Depends On:** None
- **Specs:** [Plan Format](/docs/project/specs/plan-format.md), [Plan Format Validation](/docs/project/specs/plan-format-validation.md)
- **Prototype:** None
- **Component Docs:** [IFileSystemManager](/docs/architecture/core/ports/outbound/file_system_manager.md), [ActionFactory](/docs/architecture/core/services/action_factory.md), [PlanValidator](/docs/architecture/core/services/plan_validator.md), [SessionService](/docs/architecture/core/services/session_service.md), [TextualPlanReviewer](/docs/architecture/adapters/inbound/textual_plan_reviewer.md)
- **Scope Slug:** `move-delete-actions`

## Goal
Teach the plan protocol to rename and remove files or directories as first-class actions, and keep the live context manifests truthful when it does, so a reviewer never sees a manifest that points at a path the run just renamed or deleted.

## Context
- `ActionType` (`src/teddy_executor/core/domain/models/plan.py`): Declares `CREATE`, `READ`, `EDIT`, `EXECUTE`, `RESEARCH`, and `MESSAGE` only. There is no `MOVE` and no `DELETE`, so both are new protocol members rather than new implementations of an existing one.
- Registration sites: `core/domain/models/plan.py`, `core/domain/models/__init__.py`, `core/services/action_parser_complex.py`, `core/services/markdown_plan_parser.py`, `core/services/validation_rules/helpers.py`, `core/services/session_lifecycle_manager.py`, `core/services/session_service.py`, and `adapters/inbound/textual_plan_reviewer_helpers.py` all switch on action type, so a new member must be handled in each or it will fall through silently.
- Manifest writers: `SessionService` owns `turn.context` and `session.context`, including `_append_to_session_context` and the pruning path that rewrites `session.context` sorted, so the rename and removal rewrites belong beside them rather than in the actions.
- Boolean coercion precedent: `CREATE` coerces `Overwrite` to a boolean during parsing, so `DELETE` must coerce `Recursive` the same way or `Recursive: false` arrives as a truthy non-empty string.
- Contract, MOVE: Takes `Source` and `Destination`, validates that the source exists and the destination does not, creates missing destination parents, and rewrites the live manifests so the old path becomes the new one. A rename is a `MOVE` within the same parent.
- Contract, DELETE: Takes `Path` plus an optional `Recursive`, required for a directory that is not empty, validates that the path exists, and removes the path — for a directory, every entry beneath its prefix — from the live manifests.
- Immutability boundary: Only the live `turn.context` and `session.context` are rewritten; archived session directories stay untouched, because rewriting history would falsify old payloads.
- Reviewer participation: The reviewer renders parameters and previews per action type, so an unhandled `MOVE` or `DELETE` would show an actionable node with no detail and no preview.

## Scenarios

> As a reviewer, I want a rename to keep the plan readable and the manifest accurate.

```gherkin
Given turn.context listing src/app/old_name.py and a plan with a MOVE from src/app/old_name.py to src/app/new_name.py
When the action executes
Then src/app/new_name.py exists and the old path is gone
And turn.context lists src/app/new_name.py instead of src/app/old_name.py
```

> As a reviewer, I want a deletion to leave no dangling manifest entry.

```gherkin
Given session.context listing docs/notes/scratch.md and a plan with a DELETE for that path
When the action executes
Then the file is gone
And session.context no longer lists it
```

> As a planner, I want a directory removal to be explicit rather than accidental.

```gherkin
Given a non-empty directory src/app/legacy
When a plan issues DELETE with Path src/app/legacy and Recursive false
Then validation fails with an error naming the Recursive flag
```

## Edge Cases
- **Destination occupied**: If the MOVE destination already exists, then validation fails before any filesystem change, because a half-applied rename is worse than a rejected plan.
- **Missing source**: If the MOVE source or the DELETE path does not exist, then validation fails naming the path, because a silently skipped removal would hide a planner mistake.
- **Directory rename**: If MOVE targets a directory, then every manifest entry under the old prefix is rewritten, because a directory move relocates its whole subtree.
- **Directory delete**: If DELETE targets a directory with `Recursive: true`, then every manifest entry under that prefix is removed, because leaving descendants behind produces entries for paths that no longer exist.
- **Recursive omitted**: If DELETE targets a non-empty directory without `Recursive`, then validation fails, because the destructive case must be requested explicitly.
- **Recursive as string**: If `Recursive: false` arrives, then it coerces to `False`, because the raw string is truthy and would otherwise delete recursively by accident.
- **Empty directory**: If DELETE targets a directory that is empty, then `Recursive` is not required, because nothing is destroyed implicitly.
- **Path outside the project root**: If a path escapes the root, then validation rejects it, because manifests only ever carry project-relative paths.
- **Manifest absent entry**: If the moved or deleted path appears in neither manifest, then the manifests are rewritten unchanged, because the sync must be idempotent.
- **Archived session**: If the path appears in an archived session's manifest, then it stays untouched, because history is immutable.
- **Rename onto itself**: If `Source` and `Destination` are equal, then validation rejects the action, because it is a no-op that would rewrite manifests for nothing.

## Key Unknowns
- [ ] [Technical] File-system port capability: does `IFileSystemManager` already expose a move or delete primitive, or only create/read/edit? Design Sensitivity: if a move primitive exists → the actions delegate and the slice adds only the manifest sync; if not → the slice extends the port, the local adapter, and the in-memory fake first, which makes the port extension the Interface deliverable and pushes both actions to the Adapter tier.

## Impact
1. `[EXTEND]` `ActionType` — add `MOVE` and `DELETE` with their contract strings in the plan-format spec.
2. `[EXTEND]` `IFileSystemManager` and `LocalFileSystemAdapter` — the move and removal primitives the actions need, plus the matching fake capability.
3. `[MIGRATE]` `action_parser_complex.py` and `markdown_plan_parser.py` — parse both types and coerce `Recursive` to a boolean.
4. `[MIGRATE]` `validation_rules/helpers.py` — validation for source existence, destination absence, non-empty directory recursion, self-rename, and root escape.
5. `[MIGRATE]` `session_lifecycle_manager.py` and `session_service.py` — manifest rewrite hooks for rename and removal over both manifests.
6. `[MIGRATE]` `textual_plan_reviewer_helpers.py` — parameter rendering and preview for both types.
7. `[MIGRATE]` Plan-format and plan-format-validation specs, plus the `ActionFactory`, `PlanValidator`, and `SessionService` component pages.

## Deliverables
- [ ] **Interface** — Extend `ActionType`, `IFileSystemManager`, and the plan-format specs with the two types and the move/remove primitives, and update the in-memory fake so every later tier has its double.
- [ ] **Harness** — Extend `MarkdownPlanBuilder` with MOVE and DELETE builders and the validation-error scenarios, so no test hardcodes the new Markdown.
- [ ] **Core** — Parse and validate both types, including `Recursive` coercion, and prove every rejection branch through the validator.
- [ ] **Adapter** — Implement both actions against the port, then rewrite the live `turn.context` and `session.context` for renames and removals.
- [ ] **Wiring** — Render both types in the reviewer so a reviewer can inspect and edit the parameters before approving.
- [ ] **Cleanup** — Update the two specs, the affected component pages, and the Ubiquitous Language, which currently lists only the six existing action types.

## Implementation Notes

## Verification
1. **Rename with manifest sync:**
   Create a scratch file, add it to `turn.context`, and run a plan with a MOVE to a new name.
   Verify the file moved and `turn.context` lists only the new path.
2. **Recursive delete:**
   Remove a non-empty directory with `Recursive: true` and verify the directory and its manifest entries are gone.
3. **Guardrail on destruction:**
   Issue the same delete with `Recursive: false` and verify validation fails before anything is removed.
