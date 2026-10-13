# Slice: Fix `make push` CI Attribution and CI-Registration Lag
- **Status:** Planned
- **Milestone:** N/A (ad-hoc)
- **Specs:** N/A
- **Prototype:** N/A
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

## Edge Cases

- **Push fast-forwards without a new commit**: If the pushed SHA already equals the pre-push base, then the comparison against the base still runs (and reports PASSED / pre-existing), because the base capture is taken from the remote tip, not from HEAD.
- **Base never registered (brand-new branch)**: If `gh run list --commit <BASE>` yields no run, then the target keeps its fail-safe behavior (treat as yours / block), because an unknown base must never silently pass.
- **CI registration slower than the retry budget**: If the run for the SHA still has not appeared after the bounded retry, then the target proceeds with the same fail-safe semantics and reports the situation, because silently passing is worse than a noisy block.
- **No CI configured**: If no workflow runs for the SHA, then the target does not hang past the retry budget.

## Key Unknowns

- [x] [Technical] The defect is confirmed by inspection of `Makefile` `push`: `BASE=$$(git rev-parse origin/main)` is read AFTER `git push`, so the pushed SHA advances `origin/main` and `BASE` collapses onto `SHA`.
  - **Design Sensitivity:** if the base were captured correctly → the comparison is meaningful; it is not, so the fix must move the capture before the push.
- [ ] [Technical] How to make the Makefile shell logic unit-testable: either (a) invoke the recipe in a scratch repo with fake `git`/`gh` shims via a spike, or (b) extract the attribution block into a testable script under `scripts/`. Resolve at Orientation of THIS slice (before implementation).
  - **Design Sensitivity:** if (a) → no production structure change; if (b) → a `Refactor` deliverable precedes the `Logic` fix and `make push` gains a script dependency.

## Implementation Plan

To be finalized at this slice's Orientation (the active slice is 00-35). The intended shape: capture the base ref immediately after `git pull --rebase` and BEFORE `git push`, then attribute using that captured base; add a bounded wait/retry around the `gh run list --commit <SHA>` discovery so registration lag cannot silently misclassify a regression. Mirror any Makefile change into both `makefile.md` template trees.

## Deliverables

- [ ] **Logic** - Capture the base ref (`origin/main`) BEFORE `git push` in the `make push` recipe, so attribution compares against the pre-push remote tip.
- [ ] **Logic** - Add a bounded wait/retry for CI run registration around the `gh run list --commit <SHA>` discovery.
- [ ] **Cleanup** - Sync the change into both `makefile.md` template trees ([docs/templates/makefile.md](/docs/templates/makefile.md) and [src/teddy_executor/resources/templates/makefile.md](/src/teddy_executor/resources/templates/makefile.md)).

## Implementation Notes

## Verification

1. Automated check of the attribution logic (recipe-with-shims spike or extracted-script test, per the resolved Key Unknown).
2. `make test` (full suite, no filters) is GREEN.
3. Manual (spike/scratch remote): a deliberately failing pushed commit whose base was green is reported as YOUR regression (non-zero exit).
4. Manual: a pre-existing base failure is reported as pre-existing (zero exit).
5. Manual: both `makefile.md` template trees stay aligned with the implementation.
