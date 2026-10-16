# Slice: Stem-Aware Prompt Drift Classification
- **Status:** In Progress
- **Milestone:** Ad-hoc (not tracked in the Roadmap per PROJECT.md)
- **Depends On:** None
- **Specs:** N/A
- **Prototype:** N/A (the Case File carries a verified sandbox replica)
- **Component Docs:** [InitService](/docs/architecture/core/services/init_service.md)
- **Scope Slug:** `stem-aware-drift`

## Business Goal
A user who migrated from the XML prompt era keeps `.xml` prompt files in `.teddy/prompts/` and no `.md` files. The `teddy start` preflight must report those prompts as DIFFERING from the bundled defaults, not as MISSING. This slice makes the drift check and the prompt copy routine share one stem-membership predicate, so the two sibling routines cannot diverge again.

## Scenarios
> As a user upgrading from an XML prompt set, I want the preflight to report my old `.xml` prompts as drifted so the advice stays truthful.

```gherkin
Given .teddy/prompts/ contains pathfinder.xml and no pathfinder.md
When I run `teddy start`
Then the preflight reports the prompts as differing from this version's defaults
And the advice names `teddy init prompts`
```

## Edge Cases
- **Same-stem `.xml` is drift, not missing**: If `.teddy/prompts/` holds only `pathfinder.xml`, then `pathfinder.md` reports as EDITED, because a same-stem file diverges from the bundled `.md` default.
- **Absent prompts directory**: If `.teddy/prompts/` does not exist, then every manifest prompt reports as MISSING, because the shared stem scan is guarded by a directory-existence check (`LocalFileSystemAdapter.list_directory` raises `FileNotFoundError` on an absent directory).
- **Templates keep exact-name matching**: If a template stem carries a different extension, then the template drift check still reports the `.md` as missing, because only the prompts channel opts into stem identity.
- **`.md` present and identical**: If a manifest `.md` exists and equals the bundled default, then no drift is reported, because the exact-name path is unchanged.
- **Mixed old and new prompts**: If `.teddy/prompts/` holds some `.xml` files and some `.md` files, then each manifest entry classifies independently: a same-stem `.xml` is EDITED, a matching `.md` is clean, and a truly absent `.md` is MISSING.

## Key Unknowns

**Taxonomy:** see template.

- [x] [Technical] Shared-predicate guard for an absent directory: RESOLVED BY DISCOVERY. `LocalFileSystemAdapter.list_directory` raises `FileNotFoundError` when the directory is absent, so the shared `_present_stems` helper MUST guard with `path_exists` first. Design Sensitivity: if the adapter tolerated an absent directory, the guard would be redundant but harmless.
- [x] [Technical] Existing stem-identity copy tests: RESOLVED BY DISCOVERY. `test_init_prompts_overwrite_replaces_same_stem_xml_with_md` and `test_init_prompts_non_overwrite_skips_when_same_stem_xml_present` already configure `list_directory` for `.teddy/prompts`; the extraction keeps them green. Design Sensitivity: if the extraction changed the scan or guard semantics, those tests would need updates.

## Impact
The fix is slice-scoped: the duplication lives only in `init_service.py`. No port signature changes. There is NO new boundary, so there is NO Wiring deliverable; the slice reuses the existing `InitService` seam.

1. `[EXPAND]` `InitService._present_stems` / `InitService._entry_is_present` — extract the shared stem-membership predicate.
2. `[MIGRATE]` `InitService._copy_bundled_files` — consume the shared predicate (behaviour preserved).
3. `[EXPAND]` `InitService._classify_drift` — add a defaulted `stem_identity` parameter.
4. `[MIGRATE]` `InitService.check_drift` — pass `stem_identity=True` for the prompts channel only.
5. `[MIGRATE]` `tests/suites/unit/core/services/test_init_service_drift.py` — invert the stale-`.xml` test and configure `list_directory`.
6. `[MIGRATE]` docs — `docs/architecture/core/services/init_service.md` and the stale note in `docs/project/slices/00-37-prompt-xml-to-md-migration.md`.

## Deliverables
Ordering follows `docs/templates/vertical-slice.md`. There is NO `Wiring` deliverable: the slice introduces no new boundary and reuses the existing `InitService` seam.

- [x] **Logic** — stem-aware prompt drift: add `_present_stems(dest_dir)` (guarded by `path_exists`) and `_entry_is_present(fname, present_stems)`; add a defaulted `stem_identity: bool = False` parameter to `_classify_drift` and classify a same-stem entry as EDITED when it is set; pass `stem_identity=True` for the prompts channel in `check_drift` only. Red: invert `test_check_drift_reports_stale_xml_as_missing_md` in `tests/suites/unit/core/services/test_init_service_drift.py` to assert the stale `.xml` reports as EDITED (not missing), and configure `list_directory` in all three drift tests (a bare mock is not iterable once the stem scan runs). Green: implement the minimal classifier change. Refactor: make `_copy_bundled_files` consume the same shared predicate so the stem-membership semantics live in exactly one place.
- [x] **Cleanup** — docs: update `docs/architecture/core/services/init_service.md` to document the shared stem predicate and the stem-aware drift classification; correct the stale "Stale `.xml` surfaced as drift" edge case and the "No `_classify_drift` change is required" note in `docs/project/slices/00-37-prompt-xml-to-md-migration.md`; run `git grep` for stale references.

## Implementation Notes
- **Root cause.** Commit `47e3d6d0` taught the prompt copy routine (`_copy_bundled_files` with `stem_identity=True`) that a same-stem file under any extension is the same logical prompt, but left the drift check (`_classify_drift`) matching by exact `.md` name. A user holding only `.xml` prompts has every prompt counted as present for copying, so `ensure_initialized` writes no `.md`, while the drift check counts every prompt as missing.
- **Systemic measure.** Extract one private predicate (`_present_stems` + `_entry_is_present`) and have BOTH `_copy_bundled_files` and `_classify_drift` consume it, so the stem-identity semantics live in exactly one place and cannot diverge again.
- **Shared predicate guard.** `_present_stems(dest_dir)` returns an empty set when `dest_dir` is absent, because `LocalFileSystemAdapter.list_directory` raises `FileNotFoundError`.
- **Prompts channel only.** Only `check_drift`'s prompts channel passes `stem_identity=True`; the templates channel keeps exact-name matching.
- **Case-File evidence.** The MRE `spikes/debug/xml-prompt-drift/01-xml-prompt-classified-missing-mre.py` prints `RESULT: FAIL` against production and `RESULT: PASS` against the replica; the classifier is the only variable.
- **Out of scope.** The other casefold-stem sites (`prompt_manager.py`, `session_repository.py`, `session_service.py`, `prompts.py`) resolve a single agent prompt file and already delegate to `core/utils/paths.prefer_markdown`. They are a different category and stay untouched.

### Deliverable 1 — As-Built (stem-aware prompt drift)
- **Shared predicate extracted:** `InitService` gained `_present_stems(dest_dir)` (returns the case-folded stems of the directory entries, guarded by `path_exists` so an absent directory yields an empty set) and `_entry_is_present(target_path, filename, present_stems)` (true when the exact file OR a same-stem sibling exists). Both sit beside the existing `_stem_key` helper.
- **Copy routine migrated:** `_copy_bundled_files` replaced its inline stem scan and membership check with `_present_stems`/`_entry_is_present`. Behaviour is preserved: the `stem_identity` policy still gates the scan, and `_prune_same_stem` still removes a stale same-stem file after a write.
- **Classifier made stem-aware:** `_classify_drift` gained a defaulted `stem_identity: bool = False` parameter. When set, it pre-scans `dest_dir` once via `_present_stems`; an entry present only as a same-stem sibling (e.g. a stale `.xml`) is reported as EDITED rather than MISSING, because it diverges from the bundled `.md` default.
- **Prompts channel only:** `check_drift` passes `stem_identity=True` for the prompts channel; the templates channel keeps exact-name matching because `present_stems` stays empty when the flag is false.
- **Red:** inverted `test_check_drift_reports_stale_xml_as_missing_md` to `test_check_drift_reports_stale_xml_as_edited_md` (asserts EDITED, not MISSING) and configured `list_directory` in all three drift tests; the file reported `1 failed, 2 passed` for the correct reason.
- **Green:** the four surgical edits above; `test_init_service_drift.py` plus `test_init_service.py` reported `24 passed`, confirming the extraction preserved copy behaviour and satisfied the stem-aware drift contract.
- **Integration gate:** `make test` reported the full suite green (1774 passed, 5 skipped).
- **Files changed:** `src/teddy_executor/core/services/init_service.py`, `tests/suites/unit/core/services/test_init_service_drift.py`.

### Deliverable 2 — As-Built (docs cleanup)
- **Component doc updated:** `docs/architecture/core/services/init_service.md` gained a "### Shared Stem Predicate" section describing `_present_stems` / `_entry_is_present` and both consumers. The stale exact-name drift claim was replaced, and the `check_drift` postconditions plus contract dependencies now describe the stem-aware prompts channel (a same-stem `.xml` reports as EDITED).
- **Stale slice corrected:** `docs/project/slices/00-37-prompt-xml-to-md-migration.md` now describes the original exact-name behaviour (a stale `.xml` classified as a missing `.md`) and points to slice 00-38 for the later stem-aware change, in the edge case, the `[EXPAND]` manifest note, the Implementation Notes bullet, and the Deliverable 2b As-Built line.
- **As-Built Component Doc:** confirmed the component doc reflects as-built reality and keeps `**Status:** Implemented`; no further edit was required beyond the Turn 13 rewrite.
- **Consistency check:** `git grep -n -E "_present_stems|_entry_is_present" -- src docs` resolves only to the production source and the updated component doc; no dangling references remain.
- **Integration gate:** `make test` reported the full suite green (1774 passed, 5 skipped).

## Verification
- [ ] **CLI:** Run `make test` and verify the full suite passes (green-to-green).
- [ ] **CLI:** Run `uv run python spikes/debug/xml-prompt-drift/01-xml-prompt-classified-missing-mre.py production` and verify it prints `RESULT: PASS - same-stem .xml prompts reported as DIFFER`.
- [ ] **CLI:** Run `git grep -n "_classify_drift"` and verify the prompts channel passes through the shared stem predicate.
- [ ] **Acceptance:** Confirm `tests/suites/acceptance/test_preflight_drift_notification.py::test_start_advises_init_prompts_when_a_prompt_has_drifted` stays green (the stale `pathfinder.xml` still drifts, now as EDITED, so the `teddy init prompts` advice still fires).
