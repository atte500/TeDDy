# Bug: XML prompt reported as missing instead of drifted
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** [docs/project/slices/00-37-prompt-xml-to-md-migration.md](/docs/project/slices/00-37-prompt-xml-to-md-migration.md)
- **Specs:** N/A

## Symptoms
Expected vs. actual behavior and minimal reproduction steps.

**Actual:** When the six agent prompts exist in `.teddy/prompts/` as `.xml` files (instead of `.md`), the startup preflight reports `6 prompts in .teddy/prompts/ are missing`. It advises `teddy init prompts`.

**Expected:** The prompts exist in a different form, so they diverge from the bundled `.md` defaults. The preflight must report that the prompts DIFFER (drifted), not that they are missing.

**Reproduction steps:** Place six `.xml` prompt files in `.teddy/prompts/` and no `.md` files, then run `teddy start` or `teddy resume`. Observe the "are missing" drift line.

## Context & Scope
### Regressing Delta
Confirmed: commit `47e3d6d0` (`feat(prompt-md-migration): migrate agent prompts to Markdown with stem-identity init`). `git show 47e3d6d0 -- src/teddy_executor/core/services/init_service.py` proves the commit added the `stem_identity` policy to `_copy_bundled_files` (the copy routine) but left `_classify_drift` (the drift check) matching by exact `.md` name.

File: `src/teddy_executor/core/services/init_service.py` (`_classify_drift` versus `_copy_bundled_files`).

### Environmental Triggers
A user who migrated from the XML prompt era retains `.xml` files in `.teddy/prompts/` while the bundled manifest lists `.md` names.

### Ruled Out
- `DriftReport` model: purely a data holder, no classification logic.
- `_format_drift_clause`: formats counts faithfully; it renders whatever `check_drift` classifies.

## Diagnostic Analysis
### Causal Model
`InitService.check_drift` delegates to `_classify_drift`, which builds `user_path = f"{dest_dir}/{fname}"` from the fixed `.md` manifest `_PROMPT_FILES`. A file is MISSING when that exact `.md` path does not exist. The copy routine `_init_prompts` instead calls `_copy_bundled_files(..., stem_identity=True)`, which treats a same-stem file under ANY extension (e.g. `.xml`) as present. The two routines therefore disagree: a stale `.xml` counts as present for copying but as missing for drift, producing the observed "6 prompts are missing" message.

### Discrepancies
- [x] Copy routine and drift check disagree on same-stem files under different extensions (stem identity vs exact `.md` name). (Resolved: `_copy_bundled_files` applies `stem_identity=True` for prompts while `_classify_drift` applied exact `.md` membership. The sandbox replica makes `_classify_drift` stem-aware, and the MRE flips from FAIL to PASS.)
- [x] Drift check reports "missing" for a prompt whose same-stem file exists but only diverges in extension. (Resolved: with a stem-aware classifier the same-stem `.xml` reports as EDITED, so the preflight clause reads `6 prompts in .teddy/prompts/ differ from this version's defaults`.)

### Investigation History
1. Located the drift message in `session_cli_handlers._format_drift_clause` and `InitService.check_drift`; traced classification to `_classify_drift`; observed exact `.md` path existence checks, which classifies a same-stem `.xml` as missing.
2. Inspected the copy routine `_copy_bundled_files`; observed `stem_identity=True` for prompts, which treats a same-stem `.xml` as present; concluded the two routines disagree.
3. Confirmed the regressing delta via `git show 47e3d6d0`; observed the commit added the `stem_identity` copy policy with no stem-awareness in `_classify_drift`.
4. Built the MRE `spikes/debug/xml-prompt-drift/01-xml-prompt-classified-missing-mre.py`; against production it printed empty `edited_prompts`, the full six-name `missing_prompts`, and `RESULT: FAIL` (clause `6 prompts in .teddy/prompts/ are missing`).
5. Built the sandbox replica `spikes/debug/xml-prompt-drift/replica_init_service.py` with a stem-aware `_classify_drift`; the first replica run still printed FAIL because the fake filesystem did not register the `.teddy/prompts` directory entry, so the replica directory scan was skipped. Registering the directory entries in the MRE made the replica print all six prompts in `edited_prompts`, empty `missing_prompts`, and `RESULT: PASS`.
6. Ran the systemic audit via `git grep -n -E "casefold|_stem_key|same_stem|stem_identity"` and `git grep -n "list_directory"`; observed the stem-identity predicate duplicated only inside `init_service.py`, while the other casefold-stem sites resolve a single agent prompt file and already share `core/utils/paths.prefer_markdown`.

## Solution
### Root Cause
Commit `47e3d6d0` taught the prompt copy routine (`_copy_bundled_files` with `stem_identity=True`) that a same-stem file under any extension is the same logical prompt. The drift check (`_classify_drift`) was left matching by exact `.md` name. The two sibling routines therefore re-implemented the same "is this manifest entry present?" predicate with different semantics. A user holding only pre-migration `.xml` prompts has every prompt counted as present for copying, so `ensure_initialized` writes no `.md`, while the drift check counts every prompt as missing. The preflight then reports `6 prompts in .teddy/prompts/ are missing`.

### Verified Fix (Sandbox Replica)
`spikes/debug/xml-prompt-drift/replica_init_service.py` adds a `stem_identity: bool = False` parameter to `_classify_drift`. When set, the method pre-scans `dest_dir` for same-stem entries and classifies a same-stem file (for example a stale `.xml`) as EDITED rather than MISSING. `check_drift` passes `stem_identity=True` for the prompts channel only, so templates keep exact-name matching.

Evidence: the MRE `spikes/debug/xml-prompt-drift/01-xml-prompt-classified-missing-mre.py` prints `RESULT: FAIL` (clause `6 prompts in .teddy/prompts/ are missing`) against production and `RESULT: PASS` (clause `6 prompts in .teddy/prompts/ differ from this version's defaults`) against the replica. The classifier is the only variable.

### Systemic Preventative Measure
Category: two sibling routines that must agree on a membership predicate over one shared manifest re-implement the predicate independently, so a change to one silently diverges from the other.

Generalized fix: extract a single private predicate in `init_service.py` (for example `_present_stems(dest_dir) -> set[str]` plus `_entry_is_present(fname, present_stems)`) and have BOTH `_copy_bundled_files` and `_classify_drift` consume it. The stem-identity semantics then live in exactly one place and cannot diverge again.

Audit: the duplication is localized to `init_service.py`, so the fix is slice-scoped, not structural. The other casefold-stem sites (`prompt_manager.py`, `session_repository.py`, `session_service.py`, `prompts.py`) resolve a single agent prompt file, not a manifest membership check, and already delegate their `.md` preference to the shared `core/utils/paths.prefer_markdown` helper. They are a different category and stay out of scope.

### Developer Follow-Up
- Update `tests/suites/unit/core/services/test_init_service_drift.py`: `test_check_drift_reports_stale_xml_as_missing_md` inverts to EDITED, and `test_check_drift_reports_every_prompt_missing_when_prompts_dir_absent` must configure `list_directory`, because a bare mock returns a non-iterable `MagicMock` once the stem-aware scan runs.
- Confirm `tests/suites/acceptance/test_preflight_drift_notification.py::test_start_advises_init_prompts_when_a_prompt_has_drifted` stays green. The stale `pathfinder.xml` still drifts (now as EDITED), so the `teddy init prompts` advice still fires.
- Update the completed slice `docs/project/slices/00-37-prompt-xml-to-md-migration.md` to the new stem-aware drift contract: the "Stale `.xml` surfaced as drift" edge case and the "No `_classify_drift` change is required" note now describe the old contract.

### Preserved Evidence
- MRE: `spikes/debug/xml-prompt-drift/01-xml-prompt-classified-missing-mre.py` (runs `production` or `replica`).
- Replica: `spikes/debug/xml-prompt-drift/replica_init_service.py`.
