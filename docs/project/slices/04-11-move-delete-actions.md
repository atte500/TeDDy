# Slice: MOVE and DELETE Actions with Manifest Sync
- **Status:** In Progress
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
- [x] [Technical] File-system port capability — resolved. `IFileSystemManager` exposes `remove_file(path)` (files only) and `move_directory(old_path, new_path)` (directories only), so a file move and a directory removal are both absent. The port extension is therefore the Interface deliverable, and both actions land at the Adapter tier: the port gains `move_path` and `remove_path` (the latter taking `recursive`), and `LocalFileSystemAdapter` implements both.

## Impact
1. `[EXTEND]` `ActionType` — add `MOVE` and `DELETE` with their contract strings in the plan-format spec.
2. `[EXTEND]` `IFileSystemManager` and `LocalFileSystemAdapter` — the move and removal primitives the actions need, plus the matching fake capability.
3. `[MIGRATE]` `action_parser_complex.py` and `markdown_plan_parser.py` — parse both types and coerce `Recursive` to a boolean.
4. `[MIGRATE]` `validation_rules/helpers.py` — validation for source existence, destination absence, non-empty directory recursion, self-rename, and root escape.
5. `[MIGRATE]` `session_lifecycle_manager.py` and `session_service.py` — manifest rewrite hooks for rename and removal over both manifests.
6. `[MIGRATE]` `textual_plan_reviewer_helpers.py` — parameter rendering and preview for both types.
7. `[MIGRATE]` Plan-format and plan-format-validation specs, plus the `ActionFactory`, `PlanValidator`, and `SessionService` component pages.
8. `[MIGRATE]` `action_factory.py` — its three hand-maintained maps (`_MARKDOWN_ACTION_MAP`, `_action_map`, `method_map`), without which an unregistered verb raises `ValueError: Unknown action type`. Also `registries/validators.py`, which registers each validator instance explicitly and assembles the `PlanValidator` composite list by hand.
9. `[MIGRATE]` The rest of the reviewer's per-type dispatch: `textual_plan_reviewer_execution.py` (parameter order), `textual_plan_reviewer_previews.py` (preview selection), and `textual_plan_reviewer_editor.py` (editable-field routing).
10. `[VERIFY]` No bundled template or prompt switches on an action type, so report rendering needs no branch. `ActionChangeSetBuilder.create_change_set` returns `None` outside `CREATE`/`EDIT`, so both new actions simply carry no diff preview — accepted, because neither rewrites bytes.

## Deliverables
- [x] **Interface** — Add `MOVE` and `DELETE` to `ActionType`, add `move_path` and `remove_path` to `IFileSystemManager` with contract tests, and implement both against a real temporary workspace. The specs already describe both types, so this deliverable changes no documentation.
- [x] **Harness** — Extend `MarkdownPlanBuilder` with `add_move` and `add_delete`, both accepting an explicit `Recursive` value including the string form a plan would carry, so no test hardcodes the new Markdown.
- [x] **Core** — Parse both types (coercing `Recursive` so the string `false` becomes `False`), register them in the parser dispatch map and the three factory maps, translate a MOVE's `Source`/`Destination` into the port's `old_path`/`new_path` in `ActionDispatcher._prepare_execution_params`, and prove every rejection branch through `MoveActionValidator` and `DeleteActionValidator` plus their registry entries.
- [ ] **Adapter** — Implement both actions against the port, then add the manifest-rewrite helpers beside `_append_to_session_context` and trigger them from `transition_to_next_turn`, which already receives the `ExecutionReport`, so only successful `MOVE`/`DELETE` logs rewrite anything and `ISessionManager` keeps its signature.
- [ ] **Wiring** — Render both types across all four reviewer modules so a reviewer can inspect and edit the parameters before approving.
- [ ] **Cleanup** — Prune whatever `move_path` and `remove_path` supersede, and sync the affected component pages plus the Ubiquitous Language action list.

## Implementation Notes

### Orientation audit
- The registration surface is wider than the original `Impact` section assumed: beyond the enum, the parser dispatch map, and the three factory maps, `registries/validators.py` needs an entry in two places and the reviewer spans four modules rather than one. Report rendering and the change-set path needed no branch.
- Manifest entries are root-relative project paths written via `to_root_relative`, so a `MOVE`'s `Source`/`Destination` and a `DELETE`'s `Path` compare directly against them after `normalize_resource_path`.
- The manifest sync is triggered from `transition_to_next_turn` rather than from the actions: it already receives the `ExecutionReport` and therefore knows which actions actually succeeded, which keeps the session layer in charge and leaves `ISessionManager` unchanged.
- No shared in-memory `IFileSystemManager` fake exists — the harness registers a bound mock and several test modules carry private `InMemoryFileSystem` classes. The new port primitives are proven against a real temporary directory, and validation tests use the existing bound mock.

### Interface deliverable
- `IFileSystemManager` gains two declarations beside their narrower neighbours: `move_path(old_path, new_path)` covers a file OR a directory, `remove_path(path, recursive=False)` likewise. Both docstrings state the raised exceptions, so the contract is readable at the port rather than only in the adapter.
- `move_path` reuses `_resolve_path`, so it inherits the project-root-relative convention instead of introducing a second path policy. It creates missing destination parents, refuses an occupied destination with `FileExistsError` before touching anything, and raises `FileNotFoundError` for a missing source.
- `remove_path` unlinks a file, calls `rmtree` when `recursive`, and falls back to `rmdir` so a non-empty directory without the flag fails with the platform's own `OSError`. It deliberately never calls `_get_ignore_spec`: ignore rules describe what context assembly skips, never what an explicit removal must spare, and filtering through them would leave `.gitignore`d files behind while reporting success. `test_remove_path_recursively_removes_ignored_files` pins that.
- `ActionType` carries `MOVE` and `DELETE` between `RESEARCH` and `MESSAGE`. The position is load-bearing: `ActionData.is_terminal` and `Plan.is_communication_turn` compare against `MESSAGE`, so a member appended after it would silently break the communication-turn check.
- Twelve contract tests live in `tests/suites/unit/adapters/outbound/test_file_system_adapter_contract.py` and drive the real adapter against `tmp_path`. The full suite reported 2807 passed and 5 skipped, confirming the enum and port extensions are purely additive.

### Harness deliverable
- `MarkdownPlanBuilder.add_move` routes both paths through the existing `_path_link` helper, so the spec's root-relative link form is emitted without a second path-formatting policy in the builder.
- `add_delete` takes `recursive: bool | str | None = None`. `None` omits the key entirely rather than rendering `Recursive: false`, because the spec's parsing rule 2 states an absent flag means `false`; rendering it unconditionally would erase the branch the parser is specified to handle. A given value renders lowercased and backticked, matching `add_execute`'s protocol-flag precedent, so a planner-supplied string `"false"` reaches `_coerce_bool` as `false` instead of surviving as a truthy string — the exact edge case the slice lists.
- The new cases assert rendered Markdown rather than a parse round-trip. That is deliberate: `MarkdownPlanParser._dispatch_map` gains its `MOVE`/`DELETE` entries in the Core deliverable, so a round-trip assertion here would fail for a reason unrelated to the builder. Proving the emitted Markdown parses is Core's obligation.
- `test_builder_supports_specialized_methods` claims to cover all actions and now enumerates the two new verbs, so the inventory case cannot silently under-count as verbs are added.
- Red produced six failures, all `AttributeError` naming `add_move` or `add_delete`, with the nine pre-existing cases still green. The full suite reported 2813 passed and 5 skipped — exactly six more than the pre-deliverable 2807 — confirming the builder change is purely additive to a driver imported across the acceptance suite.

### Core deliverable orientation
- `ActionFactory` binds verbs to port instances (`_action_map`) and to method names (`method_map`), never to action classes, so `MOVE`/`DELETE` register as `move_path`/`remove_path` against the `IFileSystemManager` the Interface deliverable implemented. The slice's Impact list assumed action classes; there are none, and the Adapter deliverable reduces to the manifest sync alone.
- `_get_action_wrapper.execute` forwards parsed params verbatim, so the spec's `Source`/`Destination` vocabulary would reach `move_path(old_path, new_path)` as unknown keywords and raise `TypeError`. The translation therefore joins the `param_map` in `ActionDispatcher._prepare_execution_params` that already maps CREATE's `file_path` and READ's `source`/`resource` onto `path`. This is the one scope addition the orientation produced, and it lands in Core because Core is where the registration lands. DELETE needs none: `Path` plus `Recursive` already matches `remove_path(path, recursive)`.
- `BaseActionValidator.can_validate` derives the verb from the class-name prefix, so `MoveActionValidator` and `DeleteActionValidator` dispatch with no change to `PlanValidator`; `filesystem.py` hosts them beside CREATE and READ.
- `coerce_action_params(params, {"recursive": bool})` routes through `_coerce_bool`, which reads only the case-insensitive text `true` as truthy, so a planner's `false` arrives as `False`. `get_child_text` returns an inline-code token's content bare, so backticks never reach the coercion.
- `mock_fs` leaves `path_exists` unset (a truthy iterable `Mock`) while defaulting `is_dir` to `False`, so every validator case sets what it depends on explicitly.

### Core deliverable
- Red reported 24 failures and 11 passes, every failure a missing-capability signature rather than a test defect: the parser raised `InvalidPlanError: Unknown action type: MOVE`/`DELETE` from `get_action_heading`, which checks a heading against the `ActionType`-derived `_valid_actions` set before `_dispatch_map` is consulted at all; `ActionFactory.create_action` raised `ValueError: Unknown action type`; both dispatcher cases returned with their port method uncalled; and all fifteen validator cases fell through to `PlanValidator`'s `"Unknown action type"`.
- `parse_move_action` and `parse_delete_action` mirror `parse_resource_action`'s metadata-list-only shape, since neither verb carries a content block. MOVE maps `Source`/`Destination` through `link_key_map`; DELETE maps `Path` through `link_key_map` and `Recursive` through `text_key_map`, then coerces it via `coerce_action_params(params, {"recursive": bool})` **only when the key is present**, so an omitted flag stays absent and the port's own `False` default applies — the spec's parsing rule 2, and the reason the string `false` cannot arrive truthy.
- Registration is three entries in `ActionFactory` and no action class: `_MARKDOWN_ACTION_MAP` gains `"MOVE": "move"` and `"DELETE": "delete"`, `_action_map` binds both internal keys to `self._file_system_manager`, and `method_map` binds them to `move_path` and `remove_path`. That absence of a class is why the Adapter deliverable reduced to the manifest sync alone.
- `ActionDispatcher._prepare_execution_params` gained one `param_map` entry, `"move": {"source": "old_path", "destination": "new_path"}`, because `_get_action_wrapper.execute` forwards kwargs verbatim and the spec's vocabulary would otherwise reach the port as unknown keywords. DELETE needed none: `Path` plus `Recursive` already matches `remove_path(path, recursive)`.
- Both validators live in `validation_rules/filesystem.py` beside CREATE and READ, and their ordering is load-bearing rather than stylistic. `MoveActionValidator` rejects a self-rename before any existence check, because a case that answers `path_exists` truthy for every path would otherwise report a no-op as an occupied destination. Both validators return immediately on the path-safety error, because unset `mock_fs.path_exists` calls answer with a truthy `Mock` and a second error would break the one-error contract. `DeleteActionValidator` decides emptiness from `list_directory` (names), never `list_directory_recursive`, whose ignore filtering describes context assembly rather than removal.
- `registries/validators.py` needed two entries, not one: the two `punq` registrations and the two `container.resolve` calls inside the composite list. Missing either leaves `PlanValidator` reporting "Unknown action type" for every MOVE and DELETE plan.
- The two parser imports and the two `_dispatch_map` entries had to land together, in one turn and one commit, because `MarkdownPlanParser.__init__` builds the map from the imported names: adding entries before the names exist raises `NameError` on every instantiation and takes the entire suite down.
- Tests: three cases added to `test_parser_basic_actions.py` (a MOVE round-trip, a DELETE omitting `Recursive`, and a DELETE coercion parameterized over `True`/`"false"`/`False`), two to `test_action_factory.py` (one per verb resolving to its port primitive), plus two new modules — `test_action_dispatcher_move_delete.py` for the translation seam and `test_validator_move_delete.py` for every rejection branch of both validators, driven through the registry-resolved composite so an unregistered validator fails there too. The filtered replay reported 35 passed, and the unfiltered gate reported 2837 passed and 5 skipped, exactly 24 more than the 2813 baseline.
- The first `make commit` attempt was rejected by `PLR0911` (seven returns, maximum six) on `MoveActionValidator.validate`, after the auto-fixers had already re-staged. The two required-parameter branches were near-identical, so they collapsed into one presence check over a `(name, value)` pair list that interpolates the first missing name into the unchanged sentence — six returns, same ordering, same messages. `DeleteActionValidator` sits at five and needed nothing. The practical budget is therefore four rejection branches plus the success return per validator.

## Verification
1. **Rename with manifest sync:**
   Create a scratch file, add it to `turn.context`, and run a plan with a MOVE to a new name.
   Verify the file moved and `turn.context` lists only the new path.
2. **Recursive delete:**
   Remove a non-empty directory with `Recursive: true` and verify the directory and its manifest entries are gone.
3. **Guardrail on destruction:**
   Issue the same delete with `Recursive: false` and verify validation fails before anything is removed.
