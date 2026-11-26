# Slice: Bounded Edit-Matcher Heuristics
- **Status:** Planned
- **Milestone:** [Milestone 7: Runtime Reliability & Boundary Purity](/docs/project/milestones/07-runtime-reliability.md)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [EditMatcher](/docs/architecture/core/services/edit_matcher.md), [EditSimulator](/docs/architecture/core/services/edit_simulator.md), [ConfigSchema](/docs/architecture/core/domain/config_schema.md)
- **Scope Slug:** `bounded-edit-matcher`

## Goal
Cap the work the matcher may spend when nothing anchors the FIND block, and say so when the cap is reached, so a large file cannot turn one EDIT into a multi-second stall or into a misleading "not found" — and make the simulator's ambiguity decision correct on its own rather than only because its current caller gates first.

## Context
- Measured cost: `gather_candidate_starts` (`validation_rules/edit_matcher_heuristics.py:10`) seeds a window at every line start when no FIND line anchors verbatim, and `_evaluate_candidates` (`validation_rules/edit_matcher.py:124`) runs a full `SequenceMatcher` ratio per window — 462 / 912 / 1,827 ms on 400 / 800 / 1,600-line files. The growth is roughly linear with a large constant, so a several-thousand-line generated file spends seconds inside a single EDIT while the user waits with no feedback.
- The second defect is an ordering one: `EditSimulator._apply_single_edit` evaluates ambiguity before the threshold check, and is correct today only because `EditMatcher` gates `is_ambiguous` on the effective threshold before reporting it. A second caller of the simulator — the reviewer's preview path is a plausible one — would inherit the wrong order and report ambiguity for a candidate that did not clear the threshold at all.
- The cap is an application parameter, so the Centralized Configuration law applies: it belongs in the configuration layer with a default, not as a module-level constant. That is why [ConfigSchema](/docs/architecture/core/domain/config_schema.md) is a component in this slice.
- Preserving behaviour is the hard part. Any cheap pre-filter changes which candidate wins in pathological cases, because `SequenceMatcher` ratios are not monotonic in a line-level ratio. The design that can be defended is a cap set far above any realistic pool, so behaviour is identical for every input below it, plus a visible truncation signal for the inputs above it — never a silent best-effort answer.
- A budget test belongs with the fix, and it should consume the latency-budget helper that [07-02](./07-02-test-suite-integrity.md) lands rather than reaching for `perf_counter` again.
- Overlaps: [07-02](./07-02-test-suite-integrity.md) owns the harness helper this slice's budget test uses; the matcher modules are untouched by Milestones 05 and 06, so no rebase risk there.

## Scenarios

> As a user, I want a large file with no anchor to fail fast rather than stall.

```gherkin
Given a 5,000-line file and a FIND block whose lines appear nowhere verbatim
When the matcher runs
Then it returns within the configured work cap
And the result reports that the candidate pool was truncated
And the validation message says so rather than "search text not found"
```

> As a maintainer, I want the cap to be invisible below its threshold.

```gherkin
Given any recorded matcher scenario whose candidate pool is below the cap
When the matcher runs with and without the cap
Then both runs select the same window with the same score
```

> As a maintainer, I want the simulator to be correct without relying on its caller.

```gherkin
Given a candidate below the effective similarity threshold
When the simulator is asked to apply it directly
Then it reports not-found rather than ambiguous
And the same answer comes from the matcher path
```

## Edge Cases
- **Cap reached**: If the pool is truncated, then the result carries an explicit truncation flag and the message names the cap, because a silent best-effort answer is indistinguishable from a genuine match.
- **Cap at or above pool size**: If the pool is exactly at the cap, then no truncation is reported, because truncation means candidates were discarded.
- **Deterministic order**: If the retained pool is a slice of the seeds, then the seeds are ordered by line number before slicing, because an unstable order makes the selected window non-reproducible across runs.
- **Config override**: If a user raises the cap, then the truncation flag disappears for the same input and the cost rises accordingly; the default is documented with the measurement that justifies it.
- **Threshold extremes**: If the threshold is `0.0`, then every candidate clears it and ambiguity is the correct verdict; if it is `1.0`, then only an exact match clears it, and the simulator must still evaluate the threshold before ambiguity.
- **Empty FIND or empty file**: If either side is empty, then the matcher short-circuits before seeding, because a pool of zero is not a truncation.
- **Ambiguity reported by validation**: If the simulator gains the threshold qualification, then the ambiguity count validation reports must not change for any recorded scenario, because two callers disagreeing about ambiguity is the bug being closed.
- **Budget test placement**: If the budget asserts a call cap on the comparison primitive, then it is stable under `xdist`; if it asserts wall clock, then it is not, and the slice uses the call-count form for the CI-relevant assertion with wall clock as a recorded local measurement only.
- **Measurement record**: If the cap is chosen, then the before-and-after figures for 400 / 800 / 1,600 lines are recorded in `## Implementation Notes`, because the milestone forbids asserting an improvement without measuring one.

## Key Unknowns
- [ ] [Technical] Whether a cheaper pre-filter can be proven superset-preserving for the thresholds in use. Design Sensitivity: if a necessary condition exists (for example a minimum line-overlap the window must contain) → the pool shrinks before scoring and no truncation flag is needed, which is strictly better than capping; if no such condition can be proven → the cap-with-visible-truncation design stands, and the slice must state plainly that it bounds worst-case cost rather than reducing it.

## Impact
1. `[MIGRATE]` `gather_candidate_starts` and `_evaluate_candidates` — an ordered seed set, a configured cap, and a truncation flag on the result.
2. `[MIGRATE]` The matcher result DTO — carries the truncation flag as a constrained value rather than a boolean parameter.
3. `[MIGRATE]` The edit-validation message — distinguishes a truncated pool from a genuine not-found.
4. `[MIGRATE]` `EditSimulator._apply_single_edit` — the threshold check precedes the ambiguity decision.
5. `[NEW]` The cap in `ConfigSchema` and the bundled configuration — one definition with a documented default.
6. `[NEW]` A budget test using the call-count form plus a recorded wall-clock measurement.
7. `[MIGRATE]` `EditMatcher`, `EditSimulator`, and `ConfigSchema` pages — record the cap's contract, the truncation flag, and the ambiguity ordering invariant.

## Deliverables
- [ ] **Interface** — Add the cap and the truncation flag to the configuration and result contracts, documenting the flag's meaning and the ordering invariant the simulator now holds on its own.
- [ ] **Harness** — Add the call-count budget test and a scenario proving identical selection below the cap.
- [ ] **Core** — Apply the ordered cap in the exhaustive tier, surface truncation through validation, and fix the simulator's evaluation order.
- [ ] **Cleanup** — Record the before-and-after measurements, the default's justification, and the ordering invariant on the three component pages.

## Implementation Notes

## Verification
1. **Cap holds:**
   Run the matcher against a 5,000-line file with an unanchorable FIND block.
   Verify it returns promptly and the message reports truncation rather than not-found.
2. **No behaviour change below the cap:**
   Run every recorded matcher scenario with the cap enabled.
   Verify identical window and score to the pre-change run.
3. **Simulator independent:**
   Call the simulator directly with a below-threshold candidate on a scratch branch.
   Verify it reports not-found, then revert.
