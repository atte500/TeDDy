# Slice: Three-Job CI with a Blocking Static-Analysis Gate
- **Status:** Planned
- **Milestone:** [Milestone 5: Quality Gate & Debt Reconciliation](/docs/project/milestones/05-quality-gate-debt-reconciliation.md)
- **Depends On:** [05-01-static-analysis-green](./05-01-static-analysis-green.md)
- **Specs:** None
- **Prototype:** None
- **Component Docs:** None. This slice changes the pipeline that gates every component, so [the CI template](/docs/templates/ci.md) is its governing contract.
- **Scope Slug:** `ci-gate-split`

## Goal
Separate the deterministic, diff-actionable checks that must block a merge from the aggregate metrics that must inform without blocking, so a type error or a banned import stops `main` while a duplication threshold or a file-length cap never freezes trunk again.

## Context
- `.github/workflows/ci.yml`: Declares exactly two jobs. `test-suite` (line 16) is blocking and carries `timeout-minutes: 10`; `quality-checks` (line 58) carries `continue-on-error: true` (line 61), so the workflow conclusion is `success` even when a step fails.
- The `quality-checks` step inventory (lines 93-198): `Secrets Check (detect-secrets)`, eight `File Hygiene` steps, `Formatter (ruff format)`, `Linter (ruff check)`, `Type Checker (mypy)`, `Security Audit (bandit)`, `Security Audit (pip-audit)`, six `Structural Check` steps (DI boundary, architecture boundaries, explicit UTF-8, no hardcoded /tmp, POSIX-only patches, raw CLI invoke), and `Check Python File Length (Max 500 Lines)`, with the duplication step following at line 206.
- Why the red never blocked: because every static gate lives in the `continue-on-error` job, the repository has been able to merge a `main` with 44 ruff findings and 10 mypy errors while CI reported `success`. All six structural hooks exit zero today, so the standing red is the linters and the type checker alone.
- The split's ordering constraint: `--threshold 0` duplication and the file-length cap are permanently red today, so moving them into a blocking job would freeze trunk at the first merge. Reconciliation must precede, or accompany, the split.
- `pip-audit` is blocked upstream by litellm's Python 3.14 cap, so it can never be green on this repository's dependency set; it belongs with the advisory checks by necessity rather than by preference.
- Archival precedent: the milestone records that the transition commit renames a job, so `make ci-watch` cannot match the new failing job name against its base run and reports "YOUR regression". The watching session must pin `BASE=` or expect red.
- Architectural law: `docs/architecture/ARCHITECTURE.md` prescribes the split in its `CI Pipeline` bullet while three other bullets (`Pre-commit Hooks`, `Type Enforcement`, and that same `CI Pipeline` bullet) still name a single non-blocking quality job, so the document contradicts itself until they are flipped in the same commit.

## Scenarios

> As a maintainer, I want a type error to block the merge.

```gherkin
Given a branch that introduces a mypy error in src/
When CI runs
Then the static-analysis job fails on every OS leg
And the workflow conclusion is failure
```

> As a maintainer, I want an aggregate metric to inform without blocking.

```gherkin
Given a branch that adds a module above the file-length cap
When CI runs
Then the quality-metrics job reports the file-length failure
And the workflow conclusion stays success
```

> As a maintainer, I want a platform-conditional defect to surface on the platform that has it.

```gherkin
Given a branch calling msvcrt.getwch without a platform guard
When CI runs
Then the Windows leg of static-analysis fails on the mypy step
And the Linux and macOS legs still report their own steps
```

> As a maintainer, I want a failing test leg not to cancel the others.

```gherkin
Given the test suite fails on macOS
When CI runs
Then the Linux and Windows legs run to completion
And the workflow reports which legs failed
```

## Edge Cases
- **Split before reconciliation**: If the static-analysis job blocks while ruff, mypy, or bandit are still red, then trunk freezes, because every merge inherits the standing red. The split therefore lands only after, or with, slice 05-01.
- **Advisory job name drift**: If a job is renamed without updating the watcher's matcher, then `make ci-watch` misattributes the first run it sees, because it compares job names across runs.
- **Windows default shell**: If the static-analysis job inherits the runner's default shell, then a bash-shebang hook invocation breaks only on Windows, because `cmd.exe` cannot parse it. Every matrix job needs an explicit bash default shell.
- **`fail-fast` default**: If the matrix keeps the default `fail-fast: true`, then a Windows failure cancels the Linux leg before its `mypy` output is read, because the matrix cancels siblings by default.
- **Missing wall-clock cap**: If the blocking static-analysis job has no `timeout-minutes`, then a hung structural check occupies a runner indefinitely, because only the test job currently carries a cap.
- **Duplication step placement**: If the duplication step is considered "static analysis" and promoted, then the job is permanently red against 1,198 standing clones, because that gate has no baseline.
- **`detect-secrets` with a stale baseline**: If the baseline is not refreshed in the same commit as the secrets that changed, then the blocking job fails on a finding that is already accepted, because the baseline is the only allowlist.
- **`pip-audit` promoted by mistake**: If a future edit moves `pip-audit` into the blocking job, then the gate is permanently red on advisories that cannot be upgraded yet.
- **Step ordering**: If a slow audit runs before a fast linter, then a developer waits a full audit to learn about a syntax error, because steps stop at the first failure.

## Key Unknowns
- [ ] [Technical] Job-name coupling in `make/ci.mk`: does the watcher hardcode `test-suite` and `quality-checks`, or read the failed job names out of the run payload? Design Sensitivity: if the names are hardcoded → the split edits the watcher in the same commit and the rename is invisible to the operator; if they are read from the payload → the split touches only the workflow, and the transition-run caveat becomes the only operational note.

## Impact
1. `[MIGRATE]` `.github/workflows/ci.yml` — replace `quality-checks` with a blocking `static-analysis` job (`ruff format`, `ruff check`, `mypy`, `detect-secrets`, `bandit`, the six structural hooks) and an advisory `quality-metrics` job (test file-length cap, duplication, `pip-audit` with its documented upstream residual), both on the existing OS matrix with `fail-fast: false`, a bash default shell, and their own `timeout-minutes`.
2. `[MIGRATE]` `docs/architecture/ARCHITECTURE.md` — flip the `CI Pipeline`, `Pre-commit Hooks`, and `Type Enforcement` bullets from a single non-blocking quality job to the three-job policy.
3. `[MIGRATE]` `make/ci.mk` — only if the watcher hardcodes job names, per the Key Unknown.
4. `[NEW]` A workflow-shape assertion in the harness — parse `ci.yml` and assert the job set, each job's `continue-on-error`, and each job's `timeout-minutes`, so a later edit cannot silently re-advisory a blocking gate.
5. `[MIGRATE]` `docs/project/PROJECT.md` — record which command surfaces a red advisory job, since `make ci-watch` is the only entry point for reading CI state.

## Deliverables
- [ ] **Interface** — Author the two job definitions against the CI template, keeping every existing step's command byte-identical so the split changes gating and never check semantics.
- [ ] **Harness** — Add the workflow-shape assertion that parses `ci.yml` into `{job: {continue_on_error, timeout_minutes, steps}}` and asserts the three-job split.
- [ ] **Wiring** — Land the workflow split and flip the three ARCHITECTURE bullets in one commit, so the document never describes a pipeline that does not exist.
- [ ] **Adapter** — Update `make/ci.mk` job matching if the Key Unknown resolves to hardcoded names.
- [ ] **Cleanup** — Record the advisory-job reading protocol in `PROJECT.md` and delete the milestone's stale statement that the split is pending.

## Implementation Notes

## Verification
1. **Blocking static gate:**
   Introduce a deliberate `mypy` error on a scratch branch and push.
   Verify the `static-analysis` job fails on all three legs and the workflow conclusion is `failure`.
2. **Advisory metrics:**
   Confirm the `quality-metrics` job runs file-length and duplication steps while the workflow still concludes `success` on a branch that trips none of the blocking checks.
3. **Watcher attribution:**
   Run `make ci-watch BASE=<previous-green-run>` on the transition commit and confirm the reported job names match the new workflow rather than the pre-split base.
