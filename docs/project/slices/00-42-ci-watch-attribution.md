# Slice: CI Watch Attribution Soundness
- **Status:** In Progress
- **Milestone:** N/A (ad-hoc slice)
- **Depends On:** N/A
- **Specs:** N/A
- **Prototype:** N/A
- **Component Docs:** [Makefile Template](/docs/templates/makefile.md)
- **Scope Slug:** `ci-watch-attribution`

## Business Goal
Make `make ci-watch` attribute remote CI failures soundly, so a Developer is not blocked by a pre-existing failure, a partial improvement, or an absent baseline, and is still blocked by a real regression. The Makefile MUST stay self-contained: the corrected logic ships inline in the `ci-watch` target, and a throwaway helper exists only to develop and test the logic before baking it in. Both Makefile template copies MUST mirror the corrected logic.

## Scenarios

> As a Developer, when my push reduces but does not clear a pre-existing blocking failure, I want ci-watch to report it as pre-existing, so I am not blocked by work that is not mine.

```gherkin
Given the base run fails jobs {TS, QC}
And my pushed run fails only {TS}
When make ci-watch attributes the pushed run
Then it reports the failure as pre-existing
And it exits 0
```

> As a Developer, when my push introduces a new blocking failure, I want ci-watch to block and name the failing step, so I fix it before concluding.

```gherkin
Given the base run fails jobs {TS}
And my pushed run fails jobs {TS, QC}
When make ci-watch attributes the pushed run
Then it reports a regression and names the failing step
And it exits 1
```

> As a Developer, on a multi-commit push whose tip run fails, I want ci-watch to compare against the last run-bearing ancestor, so I am not blocked by the tip-only run rule.

```gherkin
Given a push of three commits where only the tip has a run
When the tip run fails
Then ci-watch resolves the base as the previous push tip that has a run
And it attributes the failure against that base
```

## Edge Cases
- **Improvement (subset)**: If every newly failing job also failed on the base, then classify the failure as pre-existing, because no new blocking gate turned red.
- **Regression (superset)**: If any newly failing job did not fail on the base, then classify the failure as yours, because a blocking gate turned red.
- **Empty new failing set**: If the pushed run has no failing jobs but the base does, then classify as pre-existing, because nothing new failed.
- **Unknown conclusion**: If the run conclusion is `timed_out`, `cancelled`, or `startup_failure`, then block the session, because the gate result is unknown and fail-safe wins.
- **Explicit base override**: If `BASE=<sha>` is set, then use it verbatim, because the operator overrode resolution, and keep the existing unknown-base fail-safe.
- **No run-bearing ancestor**: If no ancestor carries a run for the workflow, then block the session, because the baseline is unknown.
- **No CI configured**: If no workflow file exists under `.github/workflows/`, then skip attribution and exit 0.
- **Downstream workflow**: If a workflow triggers from `workflow_run` and registers later, then do not attribute it to this push, because a downstream run is not a regression in this commit.

## Key Unknowns

- [x] [Technical] Self-contained target versus a testable helper: RESOLVED — the shipped logic stays inline in the `ci-watch` target, so the Makefile carries no runtime helper dependency. Design Sensitivity: a helper dependency would break the single-file tooling contract, so the logic inlines. A throwaway POSIX shell helper holds the logic during development and testing, then the logic is baked in and the helper is removed.
- [x] [Technical] Durable coverage of the shipped logic: RESOLVED — a fake `gh` test double drives the real `make ci-watch` target, so the shipped bytes are the tested bytes. Design Sensitivity: if coverage required a runtime helper, the tooling contract would weaken, so the test targets the shipped target instead.
- [x] [Technical] Base resolution source: RESOLVED — resolve the base per workflow as the most recent ancestor of `SHA` that has a run for that workflow, because CI creates runs on the push tip only. Design Sensitivity: if resolution fell back to `HEAD~1`, multi-commit pushes would fail safe against an absent base; the ancestor query removes the false block.
- [x] [Domain] Downstream workflow scope: RESOLVED — `ci-watch` answers whether a push-triggered workflow turned a blocking gate red. Design Sensitivity: if downstream `workflow_run` workflows stayed in scope, attribution would misfire on a non-regression, so the template documents the boundary.

## Impact
1. `[MIGRATE]` `Makefile` `ci-watch` target — apply the subset verdict, the blocking-conclusion set, the ancestor base resolution, and the documented push-triggered scope.
2. `[MIGRATE]` `docs/templates/makefile.md` — mirror the corrected logic and the scope documentation.
3. `[MIGRATE]` `src/teddy_executor/resources/templates/makefile.md` — mirror the corrected logic and the scope documentation, byte-identical to the project template.

## Deliverables
- [x] **Wiring** - Add a fake `gh` test double and a tracer-bullet acceptance test that runs the real `make ci-watch` target on a synthetic tip failure and asserts it reaches the shipped target and emits a verdict, proving end-to-end connectivity.
- [x] **Logic** - Create a POSIX shell helper with the corrected attribution decision and cover the edge cases with unit tests: the subset verdict, the blocking-conclusion set, and the ancestor base resolution.
- [x] **Migration** - Bake the validated helper logic into the `ci-watch` target inline, keeping the Makefile self-contained; extend the fake-`gh` acceptance test to assert the corrected verdicts; mirror the logic and the push-triggered scope note into both template copies.
- [ ] **Cleanup** - Remove the throwaway helper once its logic is baked into the Makefile.

## Implementation Notes

### Wiring (fake `gh` tracer bullet)
- `tests/harness/setup/ci_watch_fake_gh.py` writes a deterministic CI scenario and a POSIX `gh` shim. The shim serves only the subcommands the shipped target uses: `run list`, `run view`, and `run watch`. It applies the exact `--jq` programs the target passes and fails loudly on an unknown program, so the harness cannot silently drift from the target.
- `tests/suites/acceptance/test_ci_watch_attribution.py` runs the REAL shipped `Makefile` inside a throwaway `tempfile.mkdtemp()` git repository. The shim is prepended to `PATH`. This proves the shipped bytes are the tested bytes.
- The tracer bullet asserts end-to-end connectivity only: the invocation log is non-empty, the output carries a `CI:` verdict, and the blocking regression exits non-zero. Behavioural attribution assertions arrive with the Logic and Migration deliverables.
- Insight: GNU Make returns exit code 2 for any failed recipe. A blocking verdict therefore surfaces as a non-zero status rather than `1`, so the tracer-bullet assertion checks `returncode != 0`.

### Logic (POSIX attribution helper)
- `spikes/ci-watch-attribution/attribution.sh` is a throwaway POSIX `sh` helper carrying the corrected attribution decision. It exposes three subcommands: `subset-verdict <new> <old>`, `classify-conclusion <conc>`, and `resolve-base <tip> <workflow>`.
- `tests/suites/unit/test_ci_watch_attribution_helper.py` covers the three edge-case groups: seven `subset-verdict` permutations, six `classify-conclusion` values, and three `resolve-base` ancestor scenarios.
- `subset-verdict` splits both comma-separated sets in memory with `awk` and prints `pre-existing` when every new element also appears in the old set (an empty new set is a subset), else `regression`. The `awk` split reads stdin from `/dev/null` so it cannot block, and it uses no temporary files.
- `classify-conclusion` maps `success` to `pass`, `failure` to `attribute`, and every other value to `block` (fail-safe).
- `resolve-base` walks ancestors from `tip~1` and prints the first SHA carrying a run for the workflow, or nothing when none does.
- The helper is POSIX-only (no arrays, no `[[ ]]`, no `${var//}`) because the Make recipe runs under `sh` (`dash` on Linux). It remains throwaway: the Migration deliverable bakes the logic inline and the Cleanup deliverable deletes this file.

### Migration (inline ci-watch recipe)
- The corrected logic is baked inline into the `ci-watch` target in the project `Makefile`. Per-workflow ancestor base resolution replaces the hardcoded `HEAD~1`: the recipe walks `SHA~1`, `SHA~2`, and so on, and stops at the first ancestor that carries a run for that workflow, bounded by `BASE_DEPTH` (default 50).
- The conclusion check is fail-safe: only `success` passes, only `failure` attributes, and any other value (`timed_out`, `cancelled`, `startup_failure`) blocks with `STATUS=1`.
- The exact-equality `NEWFAIL`/`OLDFAIL` comparison became an in-memory `awk` subset verdict. The recipe prints `pre-existing` when every newly failing job also failed on the base, else `regression`. The `awk` split reads stdin from `/dev/null` and uses no temporary files, so the Makefile stays self-contained.
- The existing fail-safes are preserved: an absent run-bearing ancestor blocks, and a job-less base run blocks.
- `tests/suites/acceptance/test_ci_watch_attribution.py` gained three behavioural scenarios: the improvement (subset) that attributes pre-existing and exits 0, the regression (superset) that blocks, and a multi-commit push whose tip and root carry runs while `HEAD~1` carries none. The fixture now creates three commits so the multi-commit scenario has a run-bearing grandparent.
- Both template copies (`docs/templates/makefile.md` and `src/teddy_executor/resources/templates/makefile.md`) mirror the corrected recipe and the push-triggered scope note. A mirror script extracts the recipe from the shipped `Makefile` and splices it, so the three files stay consistent by construction; the two template copies are byte-identical (hash `2b9662c03c5e`).
- The `ci-watch` section documents the push-triggered scope: only push-triggered workflows are attributed; a downstream workflow that registers from a `workflow_run` event is not a regression in this commit.

## Verification
- [ ] **Improvement attribution:**
    On a base that already fails a blocking gate, push a change that fixes part of it.
    Run `make ci-watch` and verify it reports a pre-existing failure and exits 0.
- [ ] **Regression attribution:**
    Push a change that fails a blocking gate.
    Run `make ci-watch` and verify it reports a regression, names the failing step, and exits 1.
- [ ] **Multi-commit push:**
    Push more than one commit where the tip run fails.
    Run `make ci-watch` and verify it resolves the previous run-bearing ancestor instead of `HEAD~1`.
