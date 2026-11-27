# Slice: MOVE and DELETE Actions with Manifest Sync
- **Status:** Completed
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
10. `[EXTEND]` The report template — the fallback link-form headline in `execution_report.md.j2` exists for verbs the file-action arm does not name, so both new verbs fall through it: DELETE renders a working link only because it carries `path`, while MOVE carries `source`/`destination`, resolves its path to the empty string, and emits an empty link as its headline. `ActionChangeSetBuilder.create_change_set` still returns `None` outside `CREATE`/`EDIT`, so neither verb carries a diff preview — accepted, because neither rewrites bytes.

## Deliverables
- [x] **Interface** — Add `MOVE` and `DELETE` to `ActionType`, add `move_path` and `remove_path` to `IFileSystemManager` with contract tests, and implement both against a real temporary workspace. The specs already describe both types, so this deliverable changes no documentation.
- [x] **Harness** — Extend `MarkdownPlanBuilder` with `add_move` and `add_delete`, both accepting an explicit `Recursive` value including the string form a plan would carry, so no test hardcodes the new Markdown.
- [x] **Core** — Parse both types (coercing `Recursive` so the string `false` becomes `False`), register them in the parser dispatch map and the three factory maps, translate a MOVE's `Source`/`Destination` into the port's `old_path`/`new_path` in `ActionDispatcher._prepare_execution_params`, and prove every rejection branch through `MoveActionValidator` and `DeleteActionValidator` plus their registry entries.
- [x] **Adapter** — Implement both actions against the port, then add the manifest-rewrite helpers beside `_append_to_session_context` and trigger them from `transition_to_next_turn`, which already receives the `ExecutionReport`, so only successful `MOVE`/`DELETE` logs rewrite anything and `ISessionManager` keeps its signature.
- [x] **Wiring** — Render both types across all four reviewer modules so a reviewer can inspect and edit the parameters before approving.
- [x] **Cleanup** — Prune whatever `move_path` and `remove_path` supersede, and sync the affected component pages plus the Ubiquitous Language action list.
- [x] **Core (report headline)** — Route DELETE into the file-action arm and give MOVE a headline naming its source and destination, so neither verb renders an empty link, and correct the report formatter's page with it.

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

### Adapter deliverable
- The port primitives landed with Interface and no action class exists for either verb, so this deliverable reduced to the manifest sync alone: `ActionFactory` binds verbs to port methods, not to classes.
- `_sync_manifests_after_path_changes` fires once from `transition_to_next_turn`, after `_apply_execution_effects` and before the preservation fork. After, because a plan may READ or CREATE a path in the same turn it MOVEs or DELETEs it and rewriting first would leave those fresh entries stale; before, because the fork only adds the turn's own `plan.md`/`report.md`, which no plan can move.
- Rewrites are expressed as `(old_prefix, new_prefix)` pairs, where `new_prefix` of `None` means the paths disappear. `_match_prefix` returns the remainder beneath the prefix — `""` for an exact hit, `None` for no match — and matching is anchored on the `/` separator, so deleting `src/app/legacy` never claims `src/app/legacyish.py`. The relocation re-attaches that remainder to the new prefix, which is what makes a directory rename relocating its whole subtree fall out of the same code path as a single-file rename.
- Only `ActionStatus.SUCCESS` logs contribute. `_manifest_rewrites` reads `source`/`destination` for `ActionType.MOVE.value` and `path` for `DELETE` — the parsed vocabulary, never the dispatcher's translated port kwargs, because `ActionLog.params` is `action_data.params.copy()`.
- Only the plan side is normalized, through `_extract_resource_path`, matching `_apply_single_log_effect`'s precedent. `normalize_resource_path` is a no-op on a plain root-relative manifest entry, so normalizing both sides would buy nothing while rewriting stored entries would risk a mismatch against what the payload actually contained.
- `session.context` is read only behind a `path_exists` guard and rewritten only when `_apply_manifest_rewrites` reports a change, mirroring `_prune_context_paths`. A session that never listed the path therefore stays byte-identical, which is exactly what the failed-log case asserts.
- The module-level `ActionStatus` import replaced the function-local one inside `_apply_single_log_effect`, since the new helpers discriminate on the same enum.
- Five integration cases in `tests/suites/integration/core/services/test_session_service_manifest_sync.py` drive the real transition against a `tmp_path` session root: a file MOVE across both manifests, a directory MOVE, a file DELETE across both manifests, a recursive DELETE whose sibling `src/app/legacyish.py` must survive, and the failed-MOVE byte-identity guard. Red produced four failures (all `AssertionError` on the rewrite assertions) plus one trivially green guard, and Green flipped all four. The filtered run reported 89 passed across the neighbouring session-service suites; the unfiltered gate reported 2842 passed and 5 skipped, exactly five more than the 2837 baseline.

### Wiring deliverable
- `resolve_action_parameters` gained its two entries in `param_map`, and the `defaults` dict gained a `recursive: False` fallback. The `defaults` structure is a flat, global dict, which looked dangerous at first: a global `recursive` entry could render a third row in every pane. It does not, because `defaults` is only consulted *inside* the loop over `keys`, and `keys` comes from `param_map.get(action.type, [])`. The type's own key list is therefore the filter, and `defaults` is merely the fallback supplier — so a DELETE renders `recursive` and a MOVE never can.
- A MOVE is the one verb whose identity is a pair rather than a path, and `get_action_summary`'s fallback chain (`path` → `resource` → `command`) left its label empty. The MOVE arm renders `source -> destination`; `format_node_label` is its only consumer in the repository, so the branch is contained. The test asserts index order of the two paths rather than the arrow glyph, so the separator stays free to change.
- The genuinely dangerous defect was the boolean write-back. `_apply_param_edit` stored `str(new_val)` for every key outside `{"queries", "reference_files"}`, so a reviewer editing `recursive` to `false` in the inline modal stored the truthy string `"false"` — which would have reached `remove_path(path, recursive="false")` and deleted the subtree the reviewer had explicitly asked to spare. The fix routes a documented key set (`overwrite`, `match_all`, `allow_failure`, `background`, `recursive`) through `coerce_param(value, bool)`, the parser's pre-existing single truthiness rule, so no second truthiness policy exists in the viewer. The parametrized case covers all five keys because the defect class was pre-existing for the four older flags, not new with `recursive`.
- The robustness key set is defined as `BOOLEAN_PARAM_KEYS` beside the function rather than derived from a type map, because `ActionData.params` carries no per-key type information — the reviewer edits text into a dict that never declared its schema. The `coerce_param` import is function-local, matching how `textual_plan_reviewer.py` reaches core services without a module-level adapter-to-service import.
- The preview arm widened the existing `READ` arm to `("READ", "MOVE", "DELETE")` rather than adding a fifth arm calling the same function: three verbs share one read-only journey, and expressing that as one membership test keeps the chain's shape. `preview_readonly` then gained `source` as the last term of its `resource`-or-`path` OR-chain, so a READ still resolves by `resource`, a DELETE by `path`, and a MOVE by `source` with no second resolution policy.
- The MOVE preview deliberately shows the source path only. Rendering both paths would be a design addition beyond the slice's reviewer-participation requirement, and the Red pinned exactly one observable — the tooling consultation — so the delivered behaviour stays the size of the evidence.
- `preview_readonly`'s docstring claimed a single verb and a single target key, which the widened arm made false. It was corrected in the same Green turn rather than deferred, so the module cannot disagree with its own contract.
- The preview case asserts `find_editor.call_count == 1` rather than the notification text: the notice is transient UI copy, while the tooling consultation is the boundary the reviewer owns. Its targets are deliberately absent from disk, so the journey terminates at `_resolve_read_resource`'s "Resource not found" before any CLI-editor branch — which keeps the case hermetic (no subprocess, no real editor) while proving both halves of the fix at once: the chain routed there, *and* the target came back non-empty.
- Tests: two cases appended to `test_action_parameter_resolution.py`, a new `test_reviewer_move_delete_rendering.py` (7 cases: 5 parametrized write-back variants, the affirmative direction, the pair label), and a new `test_reviewer_move_delete_preview.py` (2 parametrized preview cases). Red produced 9 failures in the first batch and 2 in the second, every failure the modelled signature — `assert 'false' is False`, an empty parameter mapping, an empty label, and `assert 0 == 1` on `find_editor.call_count`. The unfiltered gate reported `2853 passed, 5 skipped`, exactly 11 more than the 2842 baseline.

### Cleanup deliverable
- The port now exposes exactly one move (`move_path`) and one removal (`remove_path`): `move_directory` and `remove_file` left both `IFileSystemManager` and `LocalFileSystemAdapter`, and four production call sites migrated onto their supersets — `session_repository.rename_session` to `move_path`; `init_service`, `session_lifecycle_manager`, and `session_service` to `remove_path`.
- The extend → migrate → prune ordering was load-bearing rather than stylistic. `rename_session` had a live caller, so a prune-first commit would have broken session renaming at runtime while every unit test still passed behind its bound mock. Interface added both supersets with no caller moved; Cleanup moved every caller and every assertion, then pruned.
- `rename_session` keeps its own destination guard: it raises `ValueError("Session '<name>' already exists.")` before reaching the port, so `move_path`'s `FileExistsError` never escapes and the caller's contract is unchanged by the swap.
- One real behavioural widening, unreachable from every current caller: `remove_file` raised `IsADirectoryError` on a directory, whereas `remove_path(path, recursive=False)` removes an *empty* one. All three callers pass a path built from a `list_directory` entry or a fixed marker filename, so no caller can hand it a directory today.
- Two `remove_file` contract cases were deleted rather than migrated, because `test_remove_path_removes_a_file` and `test_remove_path_raises_when_path_missing` already pin the same behaviour at the superset primitive. The unfiltered gate reported `2851 passed, 5 skipped` — exactly 2853 minus those two with no other movement, which is what makes the count evidence that no coverage was lost rather than merely a green light.
- `mock_fs` is protocol-specked, so an assertion left on a pruned declaration raises `AttributeError` instead of failing an assertion. That is why all five test modules were retargeted in the same commit as the prune rather than in a follow-up.
- The As-Built sweep reached eight pages beyond the two primitive pages, and the port page in particular had never documented the new primitives at all: the sync added both operations rather than renaming one. The rest were verb enumerations that the Core deliverable falsified — `action_factory.md` (the filesystem port supplies five handlers, not three), `action_parser_strategies.md` and `markdown_plan_parser.md` (four verbs through those strategies, and `partial_dispatch_map` routes seven), `action_dispatcher.md` (whose `parameter_normalization` invariant now carries the MOVE key remapping), `plan_validator.md` (the two injected strategies and their rejections), `session_service.md` (`transition_to_next_turn` records the manifest rewrite), `textual_plan_reviewer.md` (the read-only preview arm and the `BOOLEAN_PARAM_KEYS` write-back), and ARCHITECTURE.md's Ubiquitous Language `Action` entry, which now lists seven verbs.
- `rename_session`'s page postcondition needed no edit: it states the directory rename and the target-exists `ValueError`, both still true after the primitive swap.

### Report-headline finding (post-Cleanup audit)
- Measured rather than inferred: three logs rendered through the real `MarkdownReportFormatter` produced `### \`MOVE\`: [](/)`, `### \`DELETE\`: [scratch.md](/docs/notes/scratch.md)`, and `### \`DELETE\`: [notes](/docs/notes)`.
- One gate explains both outcomes. The file-action arm matches `['CREATE', 'EDIT', 'READ']`, so INSERT and DELETE fall through to the link-form fallback below it. That fallback resolves a path and wraps it in a link, which is why DELETE survives an arm it never belonged to: it carries `path`, so the link has something to wrap. MOVE carries `source`/`destination` and no `path`, so the resolved path is the empty string, its basename is the empty string, and the fallback emits `[](/)`.
- The fallback is not dead code and keeps its place: the validator accepts `prompt`, `invoke`, and `return` with no rules, so verbs with no path of their own still need a header.
- No existing test pinned either verb's rendered headline; the grep for a MOVE or DELETE report assertion returned nothing, which is why the suite reported green through the whole defect.
- The Cleanup commit was deliberately taken before this work, so the template diff stays attributable to the defect instead of disappearing inside an eleven-page documentation sync.
- The report formatter's page is stale in the same way: it states that the file actions are CREATE, EDIT, and READ, which is exactly the arm the template no longer matches.

### Report-headline deliverable
- Red produced six failures and one pass in `test_report_move_delete_headline.py`: the MOVE headline case reported `[](/)` where the pair belonged, the body case showed `- **Source:**`/`- **Destination:**` still emitted, all three DELETE cases failed on the link form, and `PROMPT` rendered its own `[](/)`. The single pass was the `Recursive` visibility guard, which was already correct because DELETE rendered its params before the change — so the pass was evidence, not a coincidence.
- Four template changes, each a one-gate edit: DELETE joined the file-action arm (a removal really is a file action, so it reads `### \`DELETE\`: scratch.md` with a `- **File Path:**` bullet, and a reader never learns a second headline shape for a path-bearing verb); MOVE gained its own arm, because it carries `source`/`destination` and no `path`, so no path-resolving arm can serve it; the fallback's `{% else %}` became `{% elif full_path %}`, leaving `target` empty for a path-less verb so the pre-existing `{% if target %}` renders the bare header; and MOVE's pair was appended to `param_ns.ignored` so it stops restating the headline.
- Suppressing the pair went through the per-type ignored list rather than a new body template, because that list already carries the same job for EXECUTE/RESEARCH's `description` and RESEARCH's `queries`. DELETE keeps its `recursive` bullet untouched, since `path` was already in the base ignored list and `recursive` never was.
- The separator mirrors `format_node_label`'s MOVE arm, so the reviewer and the report share one vocabulary instead of growing a second arrow. The test asserts the full headline string rather than the glyph alone, so the glyph itself stays free to change.
- The fallback is deliberately retained: the validator accepts `prompt`, `invoke`, and `return` with no rules, so verbs with no path of their own still need a header. The guard is what removes the empty link, which is why the `PROMPT` case exists — without it the slice could claim the empty link fixed while a report still printed one.
- Gates: `7 passed` in the new module, `126 passed` across the neighbouring formatter suites, and `2858 passed, 5 skipped` unfiltered — exactly the 2851 Cleanup baseline plus the seven new cases.
- The stale-reference sweep for this deliverable returned one hit: the formatter's page still named the three-verb arm. It now states the four-verb arm, the MOVE pair headline, and the guarded fallback, so the page and the template cannot disagree about which verbs render which headline.

### Verification audit
- Production-double sweep: no `remove_file` or `move_directory` survives anywhere in `src/` or `tests/`, so the pruned primitives left no shim behind, and no module this slice wrote carries a `TODO` or `FIXME`. Every rendered output derives from production logic; the one branch that resembles a stub is the report's guarded link-form fallback, which is required behaviour for the path-bearing verbs the plain arms do not name.
- Downstream audit: `move_path` has exactly two callers — `session_repository.rename_session` and the `ActionFactory` method map — and `remove_path` has four: `init_service`, `session_lifecycle_manager`, `session_service`, and that same map. Nothing orphaned remains and no caller still reaches a narrower primitive.
- Upstream audit: every per-verb dispatch site this slice touched names both verbs — the enum, `_MARKDOWN_ACTION_MAP`, the parser's `_dispatch_map` and its two strategies, the two validators with their registry entries, the reviewer's parameter map, its MOVE label arm, and its read-only preview arm. The sites that omit them are ones they cannot reach: `textual_plan_reviewer_execution.py`'s content-field map binds `CREATE`/`EXECUTE`/`RESEARCH` to a single editable body, a shape neither new verb has.
- Manifest-writer enumeration: `_prepare_session_context`, `_append_to_session_context`, `_prune_context_paths`, and the sync are the only writers of the two live manifests, and the first three never run on a per-action path, which confirms `transition_to_next_turn` is the sole trigger the sync needs.
- Test-hygiene inventory: 47 cases across six modules, each pinning a distinct execution path — 14 rejection branches, 2 translation cases, 5 headlines, 3 label and write-back cases, 2 preview routings, and 22 port contracts. No module restates another's invariant, and the pre-existing `format_node_label` cases pin different facts (execution-state suffix, enum stringification) than the pair-order case.
- Rule ratchet, deliberately not taken in-slice: the silent-fall-through anti-pattern that made this slice's registration surface so wide is already scheduled as [05-06](/docs/project/slices/05-06-action-registration-matrix.md), a parameterized matrix over every `ActionType` guarding exactly this delivery, which [06-08](/docs/project/slices/06-08-action-registration-collapse.md) later deletes once the surface collapses. A second guard here would be superseded by both, so the sweep above was run as a recorded one-off measurement.
- Out-of-scope debt routed: `tests/suites/unit/core/services/test_validator_create.py` carries a duplicated docstring and a duplicated `mock_fs.path_exists.return_value = True` assignment inside one test body. Its history (`e27aebd9`, `0b750e33`) predates this slice's first commit, so it is recorded under [05-03](/docs/project/slices/05-03-redundant-test-pruning.md) rather than edited inside a completion commit that owns no part of that file.

## Verification
1. **Rename with manifest sync:**
   Create a scratch file, add it to `turn.context`, and run a plan with a MOVE to a new name.
   Verify the file moved and `turn.context` lists only the new path.
2. **Recursive delete:**
   Remove a non-empty directory with `Recursive: true` and verify the directory and its manifest entries are gone.
3. **Guardrail on destruction:**
   Issue the same delete with `Recursive: false` and verify validation fails before anything is removed.
4. **Report headline:**
   Execute a plan carrying a MOVE and a DELETE, then read the turn's `report.md`.
   Verify the MOVE headline reads `### \`MOVE\`: <source> -> <destination>`, the DELETE headline uses the basename with a `- **File Path:**` bullet, and no empty `[]()` link appears anywhere.
