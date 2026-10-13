# Bug: `make push` false-positive regression attribution
- **Status:** Unresolved
- **Milestone:** N/A (ad-hoc)
- **Vertical Slice:** [docs/project/slices/00-36-push-attribution.md](/docs/project/slices/00-36-push-attribution.md)
- **Specs:** N/A

## Symptoms

**Expected.** `make push` blocks ONLY on failures the push introduced (per its own recipe contract: `base green -> new red = your regression`). A failure that already existed on the base — or that GitHub reports on a NON-BLOCKING (`continue-on-error`) job — must NOT be reported as the pusher's regression, and a run GitHub itself reports as `success` must not block the session Conclusion.

**Actual.** During the slice 00-36 Conclusion (`make push` on `35f818c7`), the target rebased cleanly, pushed successfully (`To https://github.com/atte500/TeDDy  4ffd1601..35f818c7  main -> main`), then printed:

```
Pushed 35f818c7a4ab4246f2e120ab56309b3723f9ea97 (base 4ffd16012c2c87411ed4179e34961f83eb735d63) after 2 poll(s)
CI: NEW failure (Quality Checks) — YOUR regression
make: *** [push] Error 1
```

The push therefore exited 1 and the session could not conclude cleanly — even though (a) the pushed diff is ENTIRELY DISJOINT from the files the `Quality Checks` failures are in, and (b) the `CI` RUN's own overall conclusion is `success` (`Quality Checks` is declared `continue-on-error: true`, so it cannot fail the run).

**Reproduction (as observed).**
1. Base commit `4ffd1601` carries an INVALID `.github/workflows/ci.yml` (an unquoted step name containing `: `), so its `CI` workflow cannot run — GitHub records run `38392567648` as `conclusion=failure` with an EMPTY `jobs` list.
2. Push `35f818c7`, whose only CI-relevant change is commit `21791061` making that YAML valid (quoting the step name).
3. The `CI` workflow now runs; its `Quality Checks` job fails on PRE-EXISTING violations (detect-secrets findings + 104 ruff-lint errors) in files the push never touched.
4. `make push`'s attribution compares the new run's failing-jobs set (`{"Quality Checks"}`) against the base run's (`{}`), finds them different, and reports `YOUR regression` -> exit 1.

## Context & Scope

### Regressing Delta

No source file that contains the violations changed. The false positive became REACHABLE through the interaction of two changes from slice 00-36:

- Commit `21791061` (`fix(ci): quote colon-bearing step names and align ci.md templates`) converted `.github/workflows/ci.yml` from INVALID YAML to valid YAML. Before it, `CI` could not execute on ANY commit — the base run `38392567648` is a JOB-LESS failure (empty `jobs`). After it, `CI` runs and surfaces the pre-existing `Quality Checks` violations.
- The rewritten `push:` recipe itself (slice 00-36: `37c6070a` base capture, `565adf58` no-CI short-circuit, `19075bb3` bounded retry + fail-safe) replaced the old single-call, base-after-push attribution with a per-JOB base-vs-new comparison that treats an EMPTY base failing-job set as "base green". That assumption is what mislabels the job-less base.

### Environmental Triggers

- The base commit's `ci.yml` must be invalid YAML (unquoted `: ` in a step name) so its run is JOB-LESS.
- CI must be configured (`.github/workflows/*.yml` present), or the no-CI short-circuit would exit 0 early.
- The `quality-checks` job must fail while the RUN stays `success` (its `continue-on-error: true`).
- Local `make commit` runs `pre-commit run` on STAGED files only, whereas CI's `Quality Checks` runs `pre-commit run --all-files` — so repo-wide violations are invisible locally yet fatal in CI. This asymmetry is why the violations were never seen during development.

### Ruled Out

- `jscpd` duplication on the two byte-identical template pairs (`makefile.md`, `ci.md`) — the failing step is the FAST pre-commit pass, not `Detect Code Duplication`.
- The 300-line Python file-length cap — the new acceptance test is well under it and the sweep is clean.
- The three `Test Suite (…)` matrix jobs — all `success`.
- The slice's own deliverables (Logic 1/2/3, Cleanup 1/2, Wiring) — they are disjoint from the failing files and their verification passed.

## Diagnostic Analysis

### Causal Model

The `push:` target attributes CI results by comparing the pushed run's failing-JOB set against the base run's failing-JOB set. Two latent assumptions in that comparison break here:

1. **"An empty base failing-job set means the base was GREEN."** In reality run `38392567648` (base `4ffd1601`) is a `conclusion=failure` run with an EMPTY `jobs` list — a job-less INVALID-WORKFLOW failure, not a green run. Because the recipe only special-cases a base run that is entirely ABSENT (`-z "$OLD"`), a base run that EXISTS but yields zero jobs falls through to `"$NEWFAIL" = "$OLDFAIL"` -> `{"Quality Checks"} = {}` -> false -> `YOUR regression`.
2. **"Any failing JOB is blocking."** The `quality-checks` job is `continue-on-error: true`; GitHub reports the RUN as `success`. The attribution inspects per-job conclusions only, so it blocks on a job the platform deliberately treats as non-fatal.

Either assumption alone is enough to produce the false positive; together they make it certain. The trigger is that commit `21791061` fixed the invalid workflow, so the base now has a job-less run AND the new run has a failing non-blocking job that a valid workflow would have shown all along.

### Discrepancies

- `make push` blocked, yet `gh run view 38392916612 --json jobs` shows `Quality Checks => failure` while the RUN-level `CI` conclusion is `success`. Conflict: the target's per-job attribution disagrees with GitHub's run-level verdict. (Resolved: `quality-checks` is `continue-on-error: true`, so a job failure does not fail the run — the attribution ignores `continue-on-error`.)
- The base run `38392567648` is `conclusion=failure` yet has ZERO jobs. Conflict: a failing run with no failing job. (Resolved: it is a job-less invalid-workflow failure — the base `ci.yml` was invalid YAML.)
- Base `ci.yml` line 87 is `    - name: Run Pre-commit Hooks (fast: formatters, secrets)` (UNQUOTED, invalid) while the pushed `ci.yml` line 87 is `    - name: "Run Pre-commit Hooks (fast: formatters, secrets)"` (QUOTED, valid). (Resolved: the fix that un-broke CI is `21791061`.)

### Investigation History

1. Hypothesis: the `Quality Checks` failure is one of our suspects (jscpd duplication, file-length, structural hook). Observation: `gh run view --log-failed` pinned the failing STEP to `Run Pre-commit Hooks (fast: formatters, secrets)` with failing hooks `detect-secrets` + `ruff-lint`, on files OUTSIDE the slice diff. Conclusion: all three suspects exonerated; the failure is pre-existing repo quality debt.
2. Hypothesis: our push touched the failing files or the quality-gate config. Observation: `git diff --name-only 4ffd1601 35f818c7` lists only our slice files, and the config-scoped diff (`.pre-commit-config.yaml`, `pyproject.toml`, `.secrets.baseline`, `ruff.toml`) is EMPTY. Conclusion: the push is disjoint from the failure.
3. Hypothesis: the violations pre-exist the push. Observation: `git show 4ffd1601:.githooks/check_hardcoded_tmp.py` (line 65 `stripped = line.strip()`) and `git show 4ffd1601:scripts/demo/drive.py` already contain the flagged code. Conclusion: violations are pre-existing and were masked while CI was invalid.
4. Hypothesis: base `4ffd1601` still carried the invalid (unquoted) ci.yml. Observation: `git show <base>:.github/workflows/ci.yml` line 87 is unquoted. Conclusion: confirmed.
5. Hypothesis: the base CI run is a job-less failure. Observation: `gh run view 38392567648 --json jobs` prints NO jobs; its `headSha` == `4ffd1601`, `conclusion=failure`, `workflowName=CI`. Conclusion: confirmed — the base run is a job-less invalid-workflow failure, which is what defeats the attribution's "empty base set == green" assumption.

## Solution

**Root cause (diagnosed).** The `make push` attribution in [Makefile](/Makefile) compares the pushed run's failing-JOB set against the base run's, and mislabels the result when (a) the base run exists but is JOB-LESS — an invalid-workflow failure with zero jobs, indistinguishable in the recipe from a green run because only an entirely ABSENT base run is special-cased — and/or (b) the failing job is declared `continue-on-error: true` so the RUN's own conclusion is `success`. Both conditions hold for the slice 00-36 Conclusion, so a run GitHub considers green is reported as `YOUR regression`.

**Fix directions (to be verified by the Debugger with an MRE).**
- Key the block decision off the RUN-level conclusion (`gh run view "$NEW" --json conclusion`), which already folds in `continue-on-error`: only block when the pushed RUN is `failure`.
- Distinguish three base states in the attribution — base run ABSENT, base run JOB-LESS, base run GREEN — instead of collapsing absent and job-less into the same "empty" bucket; a job-less base must never be read as "base green".
- Reconsider whether a NON-BLOCKING job (`continue-on-error`) should ever make `make push` block, given [ARCHITECTURE.md](/docs/architecture/ARCHITECTURE.md) defines `Quality Checks` as non-blocking.

**Systemic preventive measures (out of the Debugger's `make push` fix scope; for scheduling).**
- Add the missing `check-yaml` pre-commit hook — the Poka-Yoke that would have rejected the invalid base `ci.yml` in the first place (why the invalid YAML survived long enough to matter).
- Address (or explicitly document) the local-vs-CI pre-commit SCOPE asymmetry (local `pre-commit run` = staged files; CI `pre-commit run --all-files`), since it is why pre-existing repo-wide violations are invisible during development.
- Remediate the pre-existing `Quality Checks` debt separately (detect-secrets false positives + 104 ruff-lint errors incl. TID251 bare `MagicMock`/`patch` bans, C901 complexity, F841) — unrelated to `make push`, and should not be fixed inside its Case File.
