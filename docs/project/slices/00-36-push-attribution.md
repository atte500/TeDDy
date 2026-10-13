# Slice: Fix `make push` CI Attribution and CI-Registration Lag
- **Status:** In Progress
- **Milestone:** N/A (ad-hoc)
- **Specs:** N/A
- **Prototype:** [spikes/prototypes/push-attribution/](/spikes/prototypes/push-attribution/)
- **Component Docs:** [makefile.md](/docs/templates/makefile.md)
- **Scope Slug:** `push-attribution`

## Business Goal

Make `make push`'s CI attribution trustworthy: capture the base ref (`origin/main`) BEFORE the push so the base-vs-new comparison is meaningful, and tolerate CI run-registration lag so a regression the user introduced is never silently misclassified as pre-existing. Source: user request in the 00-35 session ("capture `origin/main` before `git push` and add a short wait/retry for CI registration").

## Scenarios

> As a TeDDy maintainer, I want `make push` to compare my pushed commit's CI results against the PRE-push base, so that a regression I introduced blocks the push.

```gherkin
Given origin/main points at commit B before the push
When `make push` rebases and pushes commit C
Then the base used for attribution is B, not C
```

```gherkin
Given CI has not yet registered a run for the pushed SHA
When `make push` queries CI runs
Then it retries briefly until the run appears before attributing any failure
```

```gherkin
Given the repository has no CI configured (no workflow files under `.github/workflows/`)
When `make push` rebases and pushes commit C
Then it logs a "no CI configured" notice and exits 0 (non-blocking)
```

## Edge Cases

- **Push fast-forwards without a new commit**: If the pushed SHA already equals the pre-push base, then the comparison against the base still runs (and reports PASSED / pre-existing), because the base capture is taken from the remote tip, not from HEAD.
- **Base never registered (brand-new branch)**: If `gh run list --commit <BASE>` yields no run, then the target keeps its fail-safe behavior (treat as yours / block), because an unknown base must never silently pass.
- **CI registration slower than the retry budget**: If the run for the SHA still has not appeared after the bounded retry, then the target proceeds with the same fail-safe semantics and reports the situation, because silently passing is worse than a noisy block.
- **No CI configured**: If the repository has no CI configured (no workflow files under `.github/workflows/`), then the target logs a clear "no CI configured" notice and exits 0 (non-blocking), because a CI-less repo must not be blocked on every push. This is distinct from the lagging case above: a repo WITH CI configured but whose run has not yet registered is still subject to the bounded retry and the fail-safe block.
- **Push rejected (non-fast-forward / branch protection)**: If `git push` is rejected, then the target MUST abort with a non-zero exit and MUST NOT run CI attribution, because the pushed SHA was never published. Preserved by folding `git push` into the attribution shell block behind `|| exit $$?`.
- **CI configured but the pushed SHA registers no run**: If CI is configured yet the specific SHA never registers a run within the retry budget, then the target fail-safe blocks (non-zero exit), because "configured CI that stayed silent" must never be confused with "no CI". (Probe scenario `never`.)

## Key Unknowns

- [x] [Technical] The defect is confirmed by inspection of `Makefile` `push`: `BASE=$$(git rev-parse origin/main)` is read AFTER `git push`, so the pushed SHA advances `origin/main` and `BASE` collapses onto `SHA`.
  - **Design Sensitivity:** if the base were captured correctly → the comparison is meaningful; it is not, so the fix must move the capture before the push.
- [x] [Technical] How to make the Makefile shell logic unit-testable: RESOLVED to approach (a) — drive the real recipe via `make` in a throwaway repo (REAL `git`) with a fake `gh` on PATH. Validated empirically by `spikes/prototypes/push-attribution/probe.py` and `probe_retry.py` (both `ALL PASS`); NO production structure change, `makefile.md` templates stay portable.
  - **Design Sensitivity:** (a) → no production structure change. Confirmed.
- [x] [Formal] Policy for the "no CI configured" case: RESOLVED at the Showcase Gate (2026-10-13) — a repository with no CI configured MUST log a clear "no CI configured" notice and exit 0 (non-blocking) rather than fail-safe blocking every push. Detected via the absence of workflow files under `.github/workflows/`.
  - **Design Sensitivity:** non-blocking for the no-CI case → a CI-less repo is never blocked; the fail-safe block is reserved for a repo that HAS CI configured but whose run never registers within the bounded retry budget.

## Implementation Plan

Validated empirically (probes [probe.py](/spikes/prototypes/push-attribution/probe.py) and [probe_retry.py](/spikes/prototypes/push-attribution/probe_retry.py), both `RESULT: ALL PASS`; fake GitHub CLI in [fake_gh.py](/spikes/prototypes/push-attribution/fake_gh.py)). The shape:

1. **Base capture (core defect fix).** Consolidate the attribution block so `BASE` is captured immediately after `git pull --rebase` and BEFORE `git push`, and fold `git push` into the same shell block behind `|| exit $$?` so a rejected / non-fast-forward push still aborts the target with a non-zero exit.
2. **No-CI short-circuit.** Immediately after the push, detect the absence of workflow files (`.github/workflows/*.yml` / `*.yaml`); if none exist, echo `No CI configured - skipping attribution` and `exit 0` (non-blocking). This MUST run BEFORE the retry loop so a CI-less repo never blocks.
3. **Bounded registration retry.** When CI IS configured, poll `gh run list --commit "$$SHA" --json workflowName` up to a bounded budget (`RETRY_POLLS` × `RETRY_SLEEP`, default 10 × 1s ≈ 10s) so registration lag cannot silently miss a regression; if the run still has not registered, fail safe (`exit 1`).
4. **Deterministic attribution.** Attribute per workflow: SHA → run id → per-job conclusion, blocking only on failures the push introduced (`base green → new red` = YOUR regression; `base red → new red, same jobs` = pre-existing; `unknown base` = fail-safe block).
5. **Mirror.** Apply the identical recipe to BOTH `makefile.md` template trees, which are byte-aligned today.

### Delta Analysis (exact codebase modifications)

- **[Makefile](/Makefile) `push:` target** — the sole production defect site: `BASE=$$(git rev-parse origin/main)` (line 54) is read AFTER `git push` (line 2 of the recipe). Rewrite the recipe per steps 1–4. `git pull --rebase` stays a separate recipe line.
- **[docs/templates/makefile.md](/docs/templates/makefile.md)** — already carries the corrected `push:` recipe and the new prose (verified at audit: `@BASE=$$(git rev-parse origin/main)` precedes the push). The Cleanup deliverable only verifies it stays identical to the finalized recipe.
- **[src/teddy_executor/resources/templates/makefile.md](/src/teddy_executor/resources/templates/makefile.md)** (line 147) — still carries the pre-fix recipe (`BASE` captured after the push) and the pre-fix prose; bring it into byte-alignment with the [docs/templates/makefile.md](/docs/templates/makefile.md) copy.
- **Prose-only references (no recipe change needed):** [docs/architecture/ARCHITECTURE.md](/docs/architecture/ARCHITECTURE.md) and [src/.../ARCHITECTURE.md](/src/teddy_executor/resources/templates/ARCHITECTURE.md) (line 20), [docs/project/inbox/01-harness-workflow-improvements.md](/docs/project/inbox/01-harness-workflow-improvements.md), [docs/project/tasks/03-post-commit-rebase-guard.md](/docs/project/tasks/03-post-commit-rebase-guard.md), and both `pre-commit.md` trees — all mention `make push` descriptively and remain accurate.
- **Tests:** no test pins the recipe text. [test_init_templates_command.py](/tests/suites/acceptance/test_init_templates_command.py) asserts only that template FILENAMES are scaffolded/overwritten; template CONTENT is unconstrained.

## Deliverables

Dependency-ordered. All three Logic deliverables edit the single `push:` recipe in the root [Makefile](/Makefile); the Cleanup deliverables mirror the finalized recipe into the template trees afterward.

- [x] **Logic** - In [Makefile](/Makefile), capture `BASE=$$(git rev-parse origin/main)` BEFORE `git push` and fold `git push` into the same shell block behind `|| exit $$?`, so attribution compares against the pre-push remote tip and a rejected push still aborts.
- [x] **Logic** - In [Makefile](/Makefile), add the no-CI short-circuit (absence of `.github/workflows/*.yml`/`*.yaml`) that logs `No CI configured - skipping attribution` and exits 0, placed BEFORE the retry loop.
- [x] **Logic** - In [Makefile](/Makefile), add the bounded registration retry (`RETRY_POLLS` × `RETRY_SLEEP`, default 10 × 1s) around the `gh run list --commit <SHA>` discovery, with a fail-safe `exit 1` when no run registers.
- [x] **Cleanup** - Mirror the finalized recipe into [docs/templates/makefile.md](/docs/templates/makefile.md).
- [ ] **Cleanup** - Mirror the finalized recipe into [src/teddy_executor/resources/templates/makefile.md](/src/teddy_executor/resources/templates/makefile.md) and keep both template trees byte-aligned.
- [ ] **Wiring** - Add a committed acceptance test under [tests/suites/acceptance/](/tests/suites/acceptance/) that drives the real [Makefile](/Makefile) `push` target end-to-end (throwaway git repo + a fake `gh` on `PATH`) and asserts the happy-path base-capture-before-push behavior and the no-CI short-circuit — the final behavioral gate for the slice's Gherkin scenarios. Guarded with `skipif` so it only runs where `make`, `git`, and a POSIX shim host exist, keeping the OS test matrix green.

## Implementation Notes

- **Prototype evidence:** the approved prototype [spikes/prototypes/push-attribution/](/spikes/prototypes/push-attribution/) drives the REAL recipe bodies through `make` inside throwaway git repos (REAL `git`) with a fake `gh` shim ([fake_gh.py](/spikes/prototypes/push-attribution/fake_gh.py)) prepended to PATH. [probe.py](/spikes/prototypes/push-attribution/probe.py) covers base-capture (regression / pre-existing); [probe_retry.py](/spikes/prototypes/push-attribution/probe_retry.py) covers registration lag (lag-green / lag-red / never) and the no-CI case. Both report `RESULT: ALL PASS`. `probe_retry.py` exposes knobs `--scenario {lag-green|lag-red|never|no-ci|all}`, `--poll-budget`, `--sleep`.
- **"No CI" detection heuristic:** the absence of `*.yml`/`*.yaml` under `.github/workflows/` (guarded `ls ... 2>/dev/null` + `-z`). Deliberately distinct from "CI configured but the pushed SHA registered no run" — the latter still fail-safe blocks.
- **Push-rejection semantics:** folding `git push` into the `@` shell block requires an explicit `|| exit $$?` so a rejected / non-fast-forward push still aborts the target (preserving the current behavior).
- **Retry budget:** `RETRY_POLLS ?= 10` × `RETRY_SLEEP ?= 1` ≈ a 10s fail-safe window; both are Make variables (overridable). Accepted by the user at the Showcase Gate (2026-10-13).
- **Canonical template source:** [src/teddy_executor/resources/templates/makefile.md](/src/teddy_executor/resources/templates/makefile.md) is the bundled canonical copy; [docs/templates/makefile.md](/docs/templates/makefile.md) is the project copy produced by `teddy init templates`. Keep them byte-aligned.
- **Testability (Key Unknown #2 resolved):** approach (a) verified — drive the real recipe via `make` with fakes on PATH; no production restructuring, templates stay portable.
- **No test pins the recipe text:** [test_init_templates_command.py](/tests/suites/acceptance/test_init_templates_command.py) asserts only template FILENAMES, so template-content edits are unconstrained.
- **Behavioral gate (Wiring):** a committed acceptance test drives the real `make push` target inside a throwaway repo (real `git`, fake `gh` on `PATH`) and asserts base-before-push capture plus the no-CI short-circuit. It is `skipif`-guarded so it only runs where `make`, `git`, and a POSIX shim host exist; the [probes](/spikes/prototypes/push-attribution/) remain the primary POSIX verification and are reused for the per-deliverable Red/Green checks.
- **Audit finding:** [docs/templates/makefile.md](/docs/templates/makefile.md) already carries the corrected recipe and prose (the reference target); only the root [Makefile](/Makefile) and [src/teddy_executor/resources/templates/makefile.md](/src/teddy_executor/resources/templates/makefile.md) still carry the defect.
- **Logic 1 (base capture) — implemented & verified:** `BASE=$$(git rev-parse origin/main)` is now the FIRST statement of the `@` shell block (immediately after `git pull --rebase`), with `SHA=$$(git rev-parse HEAD)` next, and `git push` folded into the same block behind `|| exit $$?` so a rejected / non-fast-forward push still aborts the target. Rationale: reading the base after the push lets the push advance `origin/main`, collapsing `BASE` onto the pushed SHA and misclassifying a real regression as pre-existing. Verified empirically by [probe_production.py](/spikes/prototypes/push-attribution/probe_production.py) driving the REAL [Makefile](/Makefile): pre-fix it observed `(base 31d91334)` (collapsed) with both assertions `[FAIL]`; post-fix it observes `(base cee760a3)` (the pre-push tip) with `RESULT: ALL PASS`.
- **Logic 2 (no-CI short-circuit) — implemented & verified:** immediately after the folded `git push || exit $$?;` and before `STATUS=0`, the recipe now runs `if [ -z "$$(ls .github/workflows/*.yml .github/workflows/*.yaml 2>/dev/null)" ]; then echo "No CI configured - skipping attribution"; exit 0; fi;` (mirroring the canonical [docs/templates/makefile.md](/docs/templates/makefile.md)). Rationale: a CI-less repository must never be blocked on `gh` discovery, and the guard MUST run BEFORE the retry loop so no `gh` call is ever made — this is deliberately distinct from "CI configured but the pushed SHA registered no run", which still fail-safe blocks. Verified empirically by [probe_production_no_ci.py](/spikes/prototypes/push-attribution/probe_production_no_ci.py) driving the REAL [Makefile](/Makefile) in a repo WITHOUT `.github/workflows/`: pre-fix it observed `gh invocations = ['run list --commit ...']` (the discovery loop ran) with two `[FAIL]` assertions; post-fix it observes `gh invocations = (none)`, logs `No CI configured - skipping attribution`, exits 0, and reports `RESULT: ALL PASS`.
- **Logic 3 (bounded registration retry) — implemented & verified:** the single-call discovery `for WF in $$(gh run list ...)` was replaced by a bounded poll loop — `STATUS=0; ATTEMPTS=0; WFS="";` then `while [ -z "$$WFS" ] && [ $$ATTEMPTS -lt $(RETRY_POLLS) ]; do WFS=$$(gh run list --commit "$$SHA" --json workflowName --jq '.[].workflowName' | sort -u); [ -n "$$WFS" ] && break; ATTEMPTS=$$((ATTEMPTS + 1)); sleep $(RETRY_SLEEP); done;` — followed by `echo "Pushed $$SHA (base $$BASE) after $$ATTEMPTS poll(s)"` and a fail-safe `if [ -z "$$WFS" ]; then echo "CI: no run registered for $$SHA after $(RETRY_POLLS) poll(s) - fail-safe block"; exit 1; fi;` before the per-workflow attribution loop (mirroring the canonical [docs/templates/makefile.md](/docs/templates/makefile.md)). Two new overridable Make variables, `RETRY_POLLS ?= 10` / `RETRY_SLEEP ?= 1`, bound the ~10s window. Rationale: under CI-registration lag the old single discovery call found no workflow, ran no attribution, and exited 0 — silently misclassifying a real regression; the bounded retry tolerates lag while the fail-safe guarantees that a configured-but-silent CI is never confused with "no CI". The retry runs strictly AFTER the no-CI short-circuit, so a CI-less repo still never invokes `gh`. Verified empirically by [probe_production_retry.py](/spikes/prototypes/push-attribution/probe_production_retry.py) driving the REAL [Makefile](/Makefile): pre-fix `lag-red`/`never` both exited 0 with only `Pushed <sha> (base <base>)` (three `[FAIL]` assertions); post-fix `lag-red` reports `after 2 poll(s)` and blocks with `YOUR regression`, `never` reports `after 10 poll(s)` with `fail-safe block` and a non-zero exit, and the probe reports `RESULT: ALL PASS`.
- **Cleanup 1 (docs template mirror) — verified (no change required):** [docs/templates/makefile.md](/docs/templates/makefile.md) already carried the finalized `push:` recipe and its prose, exactly as the slice's Delta Analysis flagged this deliverable as verification-only. Confirmed byte-for-byte: extracting the `push:` recipe body from the root [Makefile](/Makefile) (source of truth) and from the docs template, then `diff`-ing them, reported `IDENTICAL`, with `RETRY_POLLS`/`RETRY_SLEEP` present in both. The two template trees are NOT yet byte-aligned overall — the ONLY divergence is the `## Push (Deferred to Conclusion)` section (the docs copy is finalized; the [src copy](/src/teddy_executor/resources/templates/makefile.md) still carries the stale `git push`-separate, `BASE`-after-`SHA` recipe), which is Cleanup 2's scope.

## Verification

1. **Automated (probe):** `uv run python spikes/prototypes/push-attribution/probe.py`, `uv run python spikes/prototypes/push-attribution/probe_retry.py`, `uv run python spikes/prototypes/push-attribution/probe_production.py`, `uv run python spikes/prototypes/push-attribution/probe_production_no_ci.py`, and `uv run python spikes/prototypes/push-attribution/probe_production_retry.py` all print `RESULT: ALL PASS` — proving base-before-push capture, the bounded retry, and the no-CI short-circuit against real throwaway repos and against the REAL production [Makefile](/Makefile).
2. `make test` (full suite, no filters) is GREEN.
3. **Manual (spike/scratch remote):** a deliberately failing pushed commit whose base was green is reported as YOUR regression (non-zero exit).
4. **Manual:** a pre-existing base failure is reported as pre-existing (zero exit).
5. **Manual:** a rejected `git push` aborts the target with a non-zero exit (no CI attribution runs).
6. **Manual:** a repo with no CI configured logs `No CI configured` and exits 0 (non-blocking), while a repo WITH CI configured but no registered run still fail-safe blocks — proving the two cases are distinguished.
7. **Manual:** both `makefile.md` template trees stay byte-aligned with the implementation.
