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
- [▶] **Wiring** - Add a fake-`gh` acceptance scenario that pins `BASE=<sha>`, and wire the minimal `BASE ?=` override into the shipped `Makefile` so the shipped target honors it end to end.
- [ ] **Logic** - Complete the `ci-watch` override semantics in the shipped `Makefile`: use `BASE=<sha>` verbatim and keep the unknown-base fail-safe when the override carries no run. Add the bad-override acceptance scenario.
- [ ] **Logic** - Harden the update checker: guard `background_check` to swallow every error and move the cache-directory creation inside the guarded block in `write_update_cache`. Add the fail-silent unit coverage.
- [ ] **Migration** - Mirror the corrected `ci-watch` recipe and the override documentation into both template copies, byte-identical.
- [ ] **Cleanup** - Remove the two resolved debt entries from the Milestone 5 roadmap section in `docs/project/PROJECT.md`.

## Implementation Notes

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
