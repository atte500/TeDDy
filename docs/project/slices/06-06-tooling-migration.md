# Slice: Tooling Migration to `justfile` and Tested Python Helpers
- **Status:** Planned
- **Milestone:** [Milestone 6: Cross-Cutting Consolidation](/docs/project/milestones/06-cross-cutting-consolidation.md)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None
- **Component Docs:** None. This slice replaces the runner described by [the tooling template](/docs/templates/tooling.md).
- **Scope Slug:** `tooling-migration`

## Goal
Move the whole command surface onto `just`, with every recipe delegating to a tested Python helper, so the CI-watching, log-extraction, and probe workflows stop being unmaintainable shell pipelines, stop failing safe on a wait that expires before GitHub registers a run that exists, and stop living behind a second runner that a reader has to discover.

## Context
- **Decision (2026-11-26):** `just` is adopted for everything and the Makefile surface is retired rather than kept as a thin wrapper. Two command surfaces invite an agent to call the stale one, and a wrapper would preserve every shell pipeline this slice exists to remove.
- **The install path is measured, not assumed:** `uvx --from rust-just just --version` printed `just 1.59.0` here, so `uv tool install rust-just` is the documented prerequisite — it needs no compiler, no Homebrew, and behaves identically on macOS, Linux, and Windows. `uvx --from rust-just just <recipe>` runs a single recipe with no install at all, which keeps a fresh clone and a CI job usable before the tool is provisioned.
- **Blast radius is small, and measured:** no `make` invocation exists in `.github/` or `.githooks/`; CI runs `uv run pytest` directly and the post-commit gate is `.githooks/post-commit.py`. Deleting the Makefile therefore breaks no workflow and no hook. What must change with it is the developer interface plus the two documents that declare the bound commands.
- **Current surface, measured:** `Makefile` and five fragments (`base`, `ci`, `git`, `probe`, `test`) expose six targets — `commit` and `push` in `git.mk`, `ci-watch` and `logs` in `ci.mk`, `probe` in `probe.mk`, `test` in `test.mk` — plus `help` in the root. Three of them (`ci-watch`, `logs`, `probe`) share a `_preflight` prerequisite that survives as a real step in the helper layer.
- **The defect to fix while moving:** `ci-watch` and `probe` share a registration wait of `RETRY_POLLS` (10) × `RETRY_SLEEP` (2) — about 20 seconds — and on a repository pushing at this rate that window regularly expires before GitHub registers a run that did exist, so the session blocks on a false `no run registered` fail-safe. The migrated helper sizes the wait for an active trunk-based repository, exposes the default as configuration, shares one implementation between both consumers, and pins with a unit test that the fail-safe fires only after the full window expires.
- **Attribution survives the move:** `make/ci.mk` reads failing job names from the `gh run view --json jobs` payload instead of hardcoding them, resolving the current run and comparing its failing set against the nearest run-bearing ancestor. The helper keeps that contract, which is what lets [05-04](./05-04-ci-gate-split.md) split the workflow without touching the watcher.
- **The tooling template prescribes the shape:** one recipe per standard command, delegating heavy logic to `scripts/`, because embedded shell and `awk` pipelines break on Windows and cannot be unit-tested. `just` needs no `.PHONY`, loads `.env` in one directive, and turns `just --list` into `help`.
- **Output bounding is part of the requirement, not polish:** long sweeps today duplicate blocks and truncate their own heredoc tail, and an agent reads the tail to decide whether a command succeeded.
- **Documentation coupling:** `PROJECT.md`'s `## Tooling` table and the `ARCHITECTURE.md` bullets naming `make commit` and `make push` are the two declaration sites for the bound commands, so both change here — and `PROJECT.md`'s prerequisites gain the runner.

## Scenarios

> As a maintainer, I want a registered run to be found rather than declared missing.

```gherkin
Given a push whose workflow registers after 40 seconds
When the ci-watch helper waits for registration
Then it finds the run and watches it
And the fail-safe never fires
```

> As a maintainer, I want the CI-watching logic to be testable.

```gherkin
Given a recorded jobs payload with one failing blocking job
When attribution runs
Then it names that job and its failing step
And the attribution function is exercised by a unit test, not by a shell pipeline
```

> As an agent, I want a long sweep's tail to be readable.

```gherkin
Given a helper that prints many blocks
When it finishes
Then it prints a bounded number of complete blocks
And no block is cut mid-way
```

> As a contributor, I want one command surface that lists itself.

```gherkin
Given a fresh clone with just installed
When I run just --list
Then it names test, commit, push, ci-watch, logs, and probe, each with a description
```

## Edge Cases
- **Fail-safe timing**: If the window is configurable, then the default is sized for an active repository rather than the current 20 seconds, because a too-short window converts a slow registration into a false failure and a too-long one delays every session.
- **Both consumers**: If the wait is shared, then `probe` uses the same implementation and the same default, because two windows drift and the defect returns in the one nobody watches.
- **Unknown conclusion**: If a run's conclusion is missing, then attribution fails safe by declaring it blocking, because an unread run is not a green run.
- **Non-blocking failures**: If a job is marked advisory, then its failure never blocks, because [05-04](./05-04-ci-gate-split.md) makes that distinction the point of the split.
- **Dual surface**: If the `justfile` lands while `Makefile` survives, then two command surfaces exist and agents will call the stale one, so the Makefile and its fragments are deleted in the same commit.
- **Residual invocation**: If a workflow or hook invoked `make <target>`, then it would break on that commit; the measured answer is that none does, and the migration verifies it again before deleting rather than trusting this census.
- **`just` availability**: If `just` is not installed, then the runner is a new prerequisite, so the install path and the zero-install `uvx --from rust-just just` fallback are both stated in `PROJECT.md` and the README rather than discovered.
- **`--list` parity**: If `help` becomes `just --list`, then every recipe carries a description, because an undescribed recipe is invisible in the only discovery surface left.
- **Secrets in output**: If a helper prints a command line, then it redacts values matching the repository's secret patterns, because moving logic into Python must not widen what reaches a log.
- **Windows parity**: If a helper shells out, then it uses the project runtime rather than `bash`-only constructs, because the shell is the portability problem the move exists to solve.

## Key Unknowns
- None. Adoption is decided, the install path is measured on this machine, and every branch above is drivable by unit test against a recorded payload or a simulated clock.

## Impact
1. `[NEW]` `justfile` — six described recipes (`test`, `commit`, `push`, `ci-watch`, `logs`, `probe`) whose default lists them, each delegating to `scripts/tooling/`.
2. `[NEW]` `scripts/tooling/ci_watch.py` — run resolution, registration wait, workflow watching, and blocking attribution against the nearest run-bearing ancestor.
3. `[NEW]` `scripts/tooling/ci_logs.py` — failed-step extraction with timestamps, ANSI escapes, and group markers stripped.
4. `[NEW]` `scripts/tooling/commit.py` and `scripts/tooling/probe.py` — the staged auto-fix commit cycle and the debug-workflow dispatch.
5. `[NEW]` A shared preflight and output-bounding helper — fail fast on a missing prerequisite, cap what a sweep prints, and never cut a block mid-way.
6. `[NEW]` Unit tests for attribution, the registration wait's fail-safe boundary, output bounding, and secret redaction.
7. `[PRUNE]` `Makefile`, `make/base.mk`, `make/ci.mk`, `make/git.mk`, `make/probe.mk`, `make/test.mk` — deleted in the same commit as the `justfile`.
8. `[MIGRATE]` `docs/project/PROJECT.md` — the `## Tooling` table becomes the `just` binding, and the prerequisites gain the runner with its measured install path.
9. `[MIGRATE]` `docs/architecture/ARCHITECTURE.md` — the commit and push bullets that name `make commit` and `make push`.
10. `[MIGRATE]` The README's command snippets and prerequisites, so no document instructs a contributor to run a removed command.

## Deliverables
- [ ] **Env** — Document the verified install path and the zero-install fallback, add `scripts/tooling/` with the shared preflight and output-bounding helpers, and expose the registration wait as configuration.
- [ ] **Harness** — Unit-test attribution against a recorded jobs payload, the fail-safe against a window that has and has not expired, the bounding helper against a multi-block sweep, and redaction against a secret-shaped value.
- [ ] **Interface** — Land the `justfile` with one described recipe per standard command, each delegating to the helpers.
- [ ] **Wiring** — Delete the `Makefile` and its five fragments and update every bound-command table, snippet, and prerequisite in the same commit, so no document names a removed command.
- [ ] **Cleanup** — Record the migration and the retired surface in `PROJECT.md` and `ARCHITECTURE.md`, and note that tooling helpers are subject to the same gates as production code.

## Implementation Notes

## Verification
1. **One surface, self-describing:**
   Run `just --list` in a fresh clone.
   Verify it names `test`, `commit`, `push`, `ci-watch`, `logs`, and `probe`, each with a description.
2. **Fail-safe boundary:**
   Run the registration-wait unit test with a simulated slow registration.
   Verify the helper waits past the old 20-second window and the fail-safe does not fire.
3. **Attribution:**
   Run the attribution unit test against a recorded payload with a failing blocking job and a failing advisory job.
   Verify only the blocking one is reported as blocking.
4. **No stale surface:**
   Run `git grep -n "make commit\|make push\|make ci-watch\|make probe" -- docs .github .githooks README.md`.
   Verify no hit remains and that the `Makefile` and every `make/*.mk` fragment are gone.
5. **Zero-install path:**
   In a shell where `just` is not on `PATH`, run `uvx --from rust-just just test`.
   Verify the suite runs.
