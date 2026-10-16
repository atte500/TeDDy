# Slice: Logged Debt Reconciliation
- **Status:** In Progress
- **Milestone:** N/A (ad-hoc slice)
- **Depends On:** N/A
- **Specs:** N/A
- **Prototype:** N/A
- **Component Docs:** [Makefile Template](/docs/templates/makefile.md), [UpdateChecker](/docs/architecture/core/services/update_checker.md)
- **Scope Slug:** `debt-reconciliation`

## Business Goal
Resolve the two technical-debt items deferred from the CI-watch attribution slice. Honor an explicit `BASE=<sha>` override in `make ci-watch`, and make the update-checker background thread truly fail-silent so a late cache write cannot revert a valid commit. Remove both entries from the roadmap once fixed.

## Scenarios

> As a Developer who rebased or force-pushed, I want to pin the ci-watch comparison baseline, so I can attribute a run against a known commit.

```gherkin
Given a pushed run that fails a blocking job
And BASE=<sha> names an ancestor that carries a run for that workflow
When make ci-watch attributes the pushed run
Then it uses BASE verbatim as the comparison baseline
And it exits 0 when the failure is a subset of that baseline
```

> As a Developer, I want a bad BASE value to fail safe, so a wrong override cannot silently unblock a real regression.

```gherkin
Given a pushed run that fails a blocking job
And BASE=<sha> names a commit with no run for that workflow
When make ci-watch attributes the pushed run
Then it reports an unknown base
And it exits non-zero
```

> As a maintainer, I want the background update check to swallow every error, so a late write can never fail the suite or revert a commit.

```gherkin
Given the background update thread writes the cache after its owning test ends
When the cache write raises an OS error
Then background_check swallows the error and logs at debug level
And no unhandled thread exception escapes
```

## Edge Cases
- **Override present, run exists**: If `BASE=<sha>` is set and that commit carries a run for the workflow, then use it verbatim, because the operator overrode resolution.
- **Override present, no run**: If `BASE=<sha>` is set and that commit carries no run for the workflow, then block, because the baseline is unknown and fail-safe wins.
- **Override absent**: If `BASE` is unset, then resolve the base by walking ancestors, because that is the default behavior.
- **Ancestor-depth exhaustion**: If no ancestor within `BASE_DEPTH` commits carries a run, then block, because the baseline is unknown. Raise `BASE_DEPTH` or pin `BASE=<sha>` to override.
- **Cache directory creation fails**: If creating the cache parent directory raises `OSError`, then `write_update_cache` logs at debug and returns without raising, because the write is best-effort.
- **Fetch raises**: If `fetch_latest_version` raises, then `background_check` swallows it and logs at debug, because the documented contract is fail-silent.
- **Cache write raises**: If `write_update_cache` raises, then `background_check` swallows it, because the documented contract is fail-silent.

## Key Unknowns
- [x] [Technical] ci-watch override mechanics: RESOLVED — `BASE=<sha>` is a Make command-line variable, so `$(BASE)` expands verbatim. When set, the recipe uses it and keeps the unknown-base fail-safe. Design Sensitivity: if the override bypassed the fail-safe, a wrong SHA would silently unblock a real regression, so the fail-safe stays.
- [x] [Technical] Flake root cause and blast radius: RESOLVED — `background_check` violates its documented "swallows every error" contract because its body is unguarded, and `write_update_cache` calls `mkdir(parents=True, exist_ok=True)` outside its `try`. No existing test deterministically triggers the race, because no test requests the `pyfakefs` `fs` fixture and reaches a session entry point. The flake is a latent cross-test race closed by the production hardening. Design Sensitivity: if the fix required test-only changes, the production contract would remain broken.
- [x] [Domain] Slice scope: RESOLVED — both items are the logged debt the user directed to fix in-flight, so one ad-hoc reconciliation slice carries them. Design Sensitivity: the two items are independent, so either order keeps all tests green.

## Impact
1. `[MIGRATE]` `Makefile` `ci-watch` target — add `BASE ?=` and the override branch, and document the override in the section comment.
2. `[MIGRATE]` `tests/suites/acceptance/test_ci_watch_attribution.py` — add the override and the bad-override scenarios.
3. `[MIGRATE]` `src/teddy_executor/core/services/update_checker.py` — guard `background_check` and move the cache-directory creation inside the guarded block.
4. `[MIGRATE]` `tests/suites/unit/core/services/test_update_checker.py` — add fail-silent coverage for `background_check` and `write_update_cache`.
5. `[MIGRATE]` `docs/templates/makefile.md` — mirror the corrected recipe and the override documentation.
6. `[MIGRATE]` `src/teddy_executor/resources/templates/makefile.md` — mirror byte-identically.
7. `[MIGRATE]` `docs/project/PROJECT.md` — remove the two resolved Milestone 5 debt entries.

## Deliverables
- [x] **Wiring** - Add a fake-`gh` acceptance scenario that pins `BASE=<sha>`, and wire the minimal `BASE ?=` override into the shipped `Makefile` so the shipped target honors it end to end.
- [x] **Logic** - Complete the `ci-watch` override semantics in the shipped `Makefile`: use `BASE=<sha>` verbatim and keep the unknown-base fail-safe when the override carries no run. Add the bad-override acceptance scenario.
- [x] **Logic** - Harden the update checker: guard `background_check` to swallow every error and move the cache-directory creation inside the guarded block in `write_update_cache`. Add the fail-silent unit coverage, and bound the background thread lifetime at every test boundary.
- [x] **Migration** - Mirror the corrected `ci-watch` recipe and the override documentation into both template copies, byte-identical.
- [x] **Cleanup** - Remove the two resolved debt entries from the Milestone 5 roadmap section in `docs/project/PROJECT.md`, and reconcile the matching re-homed item in the Milestone 5 document.

## Implementation Notes

### Wiring (BASE override acceptance scenario and minimal Makefile override)
- The deliverable extended the `_run_ci_watch` driver in `tests/suites/acceptance/test_ci_watch_attribution.py` with an optional `base` argument. When set, the driver appends `BASE=<sha>` to the `make ci-watch` invocation, so a scenario can pin the comparison baseline through the CLI-variable boundary and share the existing harness rather than duplicating it.
- The `test_explicit_base_override_pins_the_baseline` scenario isolates the override as the only cause of the verdict. The tip repeats a failure the pinned base already carries, while the auto-resolved base (`HEAD~1`) is green. Without the override the recipe auto-resolves the green base and reports a regression; with the override it attributes the failure pre-existing and exits 0.
- The Red step failed exactly as predicted: the output read `CI: BLOCKING failure (Test Suite) — YOUR regression` with `assert 2 == 0`. That proves the shipped target ignored `BASE=<sha>` and that the scenario reaches the shipped `Makefile` bytes.
- The Green step added three edits to the shipped `Makefile`: a `BASE ?=` declaration alongside the other tunables, a usage line documenting the override, and a walk-skip guard. The shell base now seeds from `$(BASE)`, and the ancestor walk runs only while the base is still empty (`[ -z "$$BASE" ]`).
- An unset `$(BASE)` expands to an empty string, so the shell base starts empty, the walk condition stays true, and the default path is byte-for-byte unchanged. The four existing scenarios therefore stay green.
- Insight: GNU Make returns exit code 2 for any failed recipe, so a blocking verdict surfaces as a non-zero status rather than `1`.
- Deferred to the Logic deliverable: the bad-override fail-safe when the pinned SHA carries no run for the workflow. The empty-override path already preserves the existing unknown-base fail-safe.

### Logic (ci-watch override fail-safe)
- The deliverable added `test_bad_base_override_fails_safe` to `tests/suites/acceptance/test_ci_watch_attribution.py`. The scenario isolates the override as the only cause of the verdict: the auto-resolved base (`HEAD~1`) carries a run, so default resolution would attribute the failure pre-existing and exit 0, while the pinned runless `HEAD~2` must fail safe.
- The Red step failed exactly as predicted. The first assertion (`returncode != 0`) passed, and the second failed on `assert "unknown base" in result.stdout`. The captured stderr carried `ValueError: invalid literal for int() with base 10: ''`, which proved the mechanism: with the override set the recipe skips the walk, `OLD` resolves to the empty string, and the next line calls `gh run view ""` with an empty positional.
- The Green step added one guard immediately after the `OLD` resolution in the shipped `ci-watch` recipe. When `OLD` is empty, the recipe prints `BLOCKING failure (...) — pinned base has no run (unknown base) — YOUR regression` and sets `STATUS=1`.
- In the walk path `BASE` is set only when a run exists, so `OLD` is always non-empty there and the new guard never fires. The guard therefore fires only on the pinned-runless path, which leaves the default, improvement, regression, multi-commit, and override-pins paths unchanged.
- The acceptance file passed in full with `6 passed`, and the Integration gate reported `1846 passed, 5 skipped`.

### Logic (update-checker fail-silent hardening)
- The deliverable hardened `src/teddy_executor/core/services/update_checker.py` in two places. It moved `cache_path.parent.mkdir(parents=True, exist_ok=True)` inside the existing `try` in `write_update_cache`, so a directory-creation `OSError` is caught by the `OSError` branch instead of propagating. It wrapped the `background_check` body in a `try/except Exception` that logs at debug level, honoring the documented "swallows every error" contract. Both functions already used the inline `import logging` idiom, so the guards stay consistent with the file's style.
- The Red step added three unit tests to `tests/suites/unit/core/services/test_update_checker.py` and confirmed `3 failed, 23 deselected`. The directory-creation test needs no test double: a regular file at the parent path makes `mkdir(parents=True, exist_ok=True)` raise a real `FileExistsError`, because `exist_ok` only suppresses the error when the existing path is a directory. The two `background_check` tests follow the file's `monkeypatch.setattr` idiom on the module functions.
- The Green step made the two production edits, and the unit file passed in full with `26 passed`.
- A full-suite Integration run flaked once at `1 failed, 1848 passed, 5 skipped`: `test_file_system_adapter_recursion.py::test_list_directory_recursive_respects_ignores` raised `FileNotFoundError: Directory not found: .`. Four follow-up probes ruled out the update-check thread as the cause. An isolated re-run passed, five full-suite runs passed, and an autouse conftest probe that logged any live update-check thread at every test boundary reported no leaks. The flake is a separate, rare pyfakefs isolation issue, not the update-checker debt.
- The deliverable also added the autouse `_bound_background_update_thread` fixture to `tests/conftest.py` as a Poka-Yoke. It joins any live update-check thread at every test boundary, so a future test that drives a real session entry point can never leak the thread into a later `fs` test. It complements the fail-silent production guard.
- The Integration gate reported `1849 passed, 5 skipped`, which is the prior baseline of 1846 plus the three new fail-silent tests.

### Migration (template mirror and override documentation)
- The deliverable mirrored the corrected `ci-watch` recipe and the `BASE=<sha>` override documentation into both template copies. It documented the override in the `ci-watch` usage list and in the key-behaviors section of `docs/templates/makefile.md`.
- A splice script extracted the recipe block from the real `Makefile` (from `RETRY_POLLS ?= 10` through `exit $$STATUS`) and wrote it verbatim into the docs template, then copied the file over the bundled template. Byte-identity holds by construction, and the script asserts it. The splice printed `mirror OK; recipe block chars: 4142`.
- The Red step added `tests/suites/unit/test_makefile_template_mirror.py` with two guards and confirmed `1 failed, 1 passed`. The byte-identity guard passed because the two copies matched, and the recipe-containment guard failed because both copies omitted the four corrected markers (`BASE ?=`, the `BASE="$(BASE)"` seed, the walk-skip guard, and the pinned-no-run guard).
- The guard extracts the shipped block from the real `Makefile`, so it tracks the source of truth instead of a hardcoded copy. It follows the existing content-guard precedent (`test_readme_guardrail_flags.py`, `test_prompt_resource_relocation.py`) and gives the mirror durable coverage.
- The Green step made the two documentation edits and ran the splice. The mirror guard passed with `2 passed`, and the Integration gate reported `1851 passed, 5 skipped`, which is the prior baseline of 1849 plus the two new mirror-guard tests.

### Cleanup (roadmap debt removal)
- The deliverable removed the two resolved debt entries from the Milestone 5 requirements in `docs/project/PROJECT.md`: `Stabilize the Post-Commit Test Gate` and `ci-watch Explicit Base Override`. Both are fixed by the committed `ci-watch` override Logic and the update-checker fail-silent Logic.
- It also reconciled the matching re-homed item 21 in `docs/project/milestones/05-quality-gate-debt-reconciliation.md`, which asked to guard `write_update_cache` against `FileExistsError` and `NotADirectoryError`. The fail-silent hardening now moves the `mkdir` inside the `OSError` guard, so the item was removed and the remaining items were renumbered. The recursion-flake item stays open as the current item 20, because it is a separate rare pyfakefs isolation issue.
- The Turn 87 Consistency Check reported `(none)` for both removed `PROJECT.md` entry names, `(none)` for the update-checker milestone item, and `(none)` for any remaining tracked reference, so no stale reference survives.
- The Cleanup deliverable only edits documentation, so the Integration gate stayed at `1851 passed, 5 skipped`, equal to the prior baseline.

## Verification
- [ ] **Base override pins the baseline:**
    Run `make ci-watch BASE=<sha>` against a pushed run whose auto-resolved base is green.
    Verify the output reports the failure as `pre-existing` against the pinned base and exits 0.
- [ ] **Bad base fails safe:**
    Run `make ci-watch BASE=<sha>` where the SHA carries no run for the workflow.
    Verify the output reports an `unknown base` and exits non-zero.
- [ ] **Background check failure is swallowed:**
    Run `uv run python -c "from pathlib import Path; from teddy_executor.core.services.update_checker import background_check; background_check(Path('/nonexistent-root/.teddy/.update_cache.json'))"`.
    Verify the command returns without raising and prints no traceback.
