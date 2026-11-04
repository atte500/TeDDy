# Slice: Ambiguity Detection for Approximate EDIT Matches
- **Status:** Planned
- **Milestone:** N/A (ad-hoc slice)
- **Depends On:** N/A
- **Specs:** N/A
- **Prototype:** N/A
- **Component Docs:** [EditSimulator](/docs/architecture/core/services/edit_simulator.md), [PlanValidator](/docs/architecture/core/services/plan_validator.md)
- **Scope Slug:** `edit-ambiguity`

## Goal
Stop an EDIT from silently landing on the wrong block when the winning FIND match is only approximate and a second candidate is equally plausible, while keeping verbatim matches editable even when a sibling function shares the same body shape.

## Context

- `edit_matcher._refine_and_select_best`: the candidate loop sets `is_ambiguous = True` only when `ratio == best_ratio and ratio > 0 and ratio >= threshold`. A winner at `0.9948` against a runner-up at `0.9816` is accepted silently.
- `edit_matcher.find_best_match`: returns `(match_str, round(score, 2), is_ambiguous, offset)`. The tie comparison runs on the raw ratio while the reported score is rounded to two decimals, so two distinct candidates can both display `0.99`.
- `edit_matcher._apply_indentation_bonus`: promotes a window that matches after `rstrip` with one constant relative indentation offset to exactly `1.0` and returns that offset.
- `edit_matcher._apply_substring_boost`: promotes a verbatim intra-line fragment (single-line FIND) or a literal contiguous multi-line block to `1.0`, and flags ambiguity when the fragment occurs more than once inside the same window.
- `edit_matcher_heuristics.gather_candidate_starts`: Tier 1 seeds windows from up to five longest non-blank FIND lines found verbatim in the file; the Tier 2 fuzzy first-line cascade runs only when Tier 1 is empty; Tier 3 scans substrings for a single-line FIND; Tier 4 falls back to exhaustive. On real source with an injected one-character `def` typo, Tier 1 seeded exactly one candidate in all three probes.
- `edit_simulator._apply_single_edit`: raises `MultipleMatchesFoundError` when `is_ambiguous and not match_all`, computing `count = content.count(find) if score == 1.0 else 2`. It replaces `best_match` — the real file text — with the REPLACE block, so a tolerated typo cannot corrupt surrounding content.
- `validation_rules/edit.py:_validate_single_edit`: applies the same gate, `is_ambiguous and not match_all and score >= effective_threshold`. Its message carries the path, the two-decimal score, the FIND embed, and a hint — no occurrence count.
- `plan.DEFAULT_SIMILARITY_THRESHOLD = 0.95`, applied inclusively. `resolve_similarity_threshold` resolves action params first, then global config, then the default.
- `tests/suites/unit/core/services/test_edit_ambiguity_threshold_gating.py`: deliberately pins the ties-only contract — a tie at or above the threshold is "ambiguous", a tie below it is "could not be located" so the author gets the closest-match diff instead.

Observed candidate distributions at threshold `0.95`:

| Scenario | Best | Runner-up | Current rule | Naive multi-above | Refined rule |
| :-- | --: | --: | :-- | :-- | :-- |
| Verbatim FIND, near-duplicate sibling | 1.0000 | 0.9816 | accept | block | accept |
| Fuzzy FIND (one-character typo), same sibling | 0.9948 | 0.9816 | accept | block | block |
| Verbatim FIND at two locations | 1.0000 | 1.0000 | block | block | block |

Two further observations. Swapping a single character in the FIND's `def` line flipped which sibling block was edited, with `success` reported at both the simulator and the validator. And a fuzzy FIND present two, three, and five times all reported "Found 2 ambiguous occurrences".

## Scenarios

> As a developer whose FIND block carries a small typo, I want the EDIT to abort when a sibling block could equally be the target, so that I learn my FIND block is not unique instead of silently editing the wrong function.

```gherkin
Given a file holds two functions with the same body and different names
And my FIND block reproduces the body with a one-character typo in the target function's name
When the plan is validated
Then validation fails with an ambiguity error naming the offending FIND block
And the error reports how many candidates cleared the similarity threshold
And the reported score reveals the runner-up
```

```gherkin
Given a file holds two functions with the same body and different names
And my FIND block matches the target function byte for byte
When the plan is validated
Then validation passes
And the EDIT applies to that single verbatim location
```

```gherkin
Given a FIND block appears verbatim at two locations
When the plan is validated without Match All
Then validation fails with an ambiguity error reporting two occurrences
When the same edit is submitted with Match All true
Then every occurrence is replaced
```

## Edge Cases
- **Verbatim best with a near-duplicate sibling**: If the best match is exactly `1.0` and the runner-up sits above the threshold but below `1.0`, then the edit is accepted, because a byte-exact match at one location is conclusive and rejecting it would make any edit against a shared boilerplate body impossible.
- **Fuzzy best with a below-threshold runner-up**: If the best match is below `1.0` and the runner-up is below the threshold, then the edit is accepted, because only one candidate clears the acceptance floor.
- **Indentation-only drift**: If the only difference is a constant relative indentation, then the match is promoted to `1.0` and treated as verbatim, because the REPLACE block is re-indented to the matched offset and indentation-insensitive matching is intentional.
- **Tie below the threshold**: If two candidates tie below the effective threshold, then the failure is "could not be located" with the closest-match diff, not an ambiguity error, because there is nothing to disambiguate.
- **Match All requested**: If `Match All: true` is set, then ambiguity never blocks, because the author has declared intent to change every occurrence.
- **Single seeded candidate**: If Tier 1 exact anchoring yields one window, then the refined clause cannot fire, because there is no runner-up above the threshold.
- **Duplicate inside one window**: If a single-line FIND occurs twice within the same matched window, then the substring boost keeps reporting ambiguity, because two replacements inside one window are still ambiguous.
- **Rounded-equal but raw-distinct scores**: If two candidates display the same two-decimal score but differ in raw ratio, then they are not a tie, because the comparison must run on raw ratios.

## Key Unknowns

- [ ] [Domain] Carve-out boundary for whitespace-promoted matches: an indentation-only difference is promoted to `1.0`, so a whitespace-drifted match with a `0.98` sibling stays accepted. Is that the intended reading of "verbatim"? Design Sensitivity: if yes → `top < 1.0` is the whole clause and nothing else changes; if no → the clause needs a separate signal distinguishing a byte-exact winner from a whitespace-promoted one, which the matcher does not currently expose.
- [ ] [Technical] Shape of the candidate distribution in the matcher contract: widen the existing 4-tuple, or add a sibling function returning a small DTO? Design Sensitivity: if the tuple widens → three production unpack sites and roughly five test modules change in one commit; if a DTO is added → the existing tuple stays intact and only new consumers migrate, but two entry points must stay in sync.
- [ ] [Functional] Message convergence: should the executor and the validator share one ambiguity message builder? Design Sensitivity: if shared → one new helper in `validation_rules` and both call sites shrink; if separate → the executor keeps its occurrence count, the validator gains the runner-up score, and the two texts stay divergent.

## Impact

1. `[EXPAND]` `edit_matcher._refine_and_select_best` — additionally track and return the runner-up ratio and the count of candidates at or above the threshold.
2. `[EXPAND]` `edit_matcher.find_best_match` and `find_best_match_and_diff` — surface the new fields through the return contract, keeping every comparison on raw ratios and the displayed score at higher precision.
3. `[MIGRATE]` `EditSimulator._apply_single_edit` — consume the runner-up and the candidate count, deleting the hardcoded `else 2`.
4. `[MIGRATE]` `validation_rules/edit.py:_validate_single_edit` — consume the runner-up and print it in the ambiguity message.
5. `[CONTRACT]` The hardcoded `2` in the fuzzy count branch — removed once the real count is available.

## Deliverables

- [ ] **Interface** - Widen the matcher's result contract to carry the runner-up ratio and the above-threshold candidate count, keeping raw ratios for every comparison.
- [ ] **Harness** - Add shared fixtures for the three canonical scenarios (verbatim versus near-duplicate sibling, fuzzy near-tie, verbatim duplicate) plus a generator for an N-copy fuzzy duplicate.
- [ ] **Core** - Implement the refined ambiguity condition `(ties > 1 and top >= threshold) or (top < 1.0 and second >= threshold)` and reconcile `test_edit_ambiguity_threshold_gating.py` in the same commit, because that module pins the previous contract.
- [ ] **Core** - Replace the hardcoded fuzzy count with the real number of above-threshold candidates in `EditSimulator._apply_single_edit`.
- [ ] **Migration** - Print the runner-up score and the true candidate count in the validator's ambiguity message so both layers describe the same condition.
- [ ] **Cleanup** - Update the matcher and simulator suites whose assertions destructure the return contract, and remove the two-decimal rounding that lets distinct candidate scores present as an identical `0.99`.

## Implementation Notes
Every comparison must run on the raw ratio. `find_best_match` rounds only on return, so comparing rounded values would make `0.9948` and `0.9949` a false tie.

`_apply_indentation_bonus` and `_apply_substring_boost` both promote to exactly `1.0`, which makes `top < 1.0` precisely mean "no verbatim and no indentation-only match" — the intended carve-out, and the reason the refined clause cannot block a routine edit.

The rule change and the gating-test rework must land in one commit. That module deliberately asserts the ties-only contract, so shipping the rule first turns the suite red.

Tier 1 exact anchoring keeps the blast radius narrow: on real source with an injected typo, every probe seeded a single candidate. The new clause only fires where sibling blocks genuinely share body text.

The simulator replaces `best_match` — the real file text — rather than the FIND string, which is why a tolerated typo cannot corrupt surrounding content and needs no extra guard.

If a new result DTO is introduced, register it in the `ARCHITECTURE.md` component map when the slice lands.

## Verification

1. **Fuzzy near-tie is blocked:**
   Run `uv run python spikes/debug/edit-matcher-ambiguity/near_tie_probe.py`.
   Verify both `near_tie_closer_to_alpha` and `near_tie_closer_to_beta` report `ambiguous=True` and the validator classification `ambiguous`.
2. **Verbatim match stays editable:**
   Run `uv run python spikes/debug/edit-matcher-ambiguity/ambiguity_rule_verdict_probe.py`.
   Verify `verbatim_vs_near_duplicate` reports `refined: accepted` while `fuzzy_near_tie` reports `refined: AMBIGUOUS`.
3. **Occurrence count is truthful:**
   Run `uv run python spikes/debug/edit-matcher-ambiguity/ambiguity_rule_probe.py`.
   Verify the hardcoded-count section reports three distinct counts across `copies=2`, `copies=3`, and `copies=5` instead of `Found 2` three times.
4. **Ambiguity message reads correctly in the review pane:**
   Author a plan whose `EDIT` targets one of two sibling functions, with a one-character typo in the target function's `def` line, then start a session and open the plan review pane on that turn.
   Confirm the `EDIT` node is flagged, that the message names the true number of candidates that cleared the threshold rather than a fixed `2`, and that it prints the runner-up score beside the winning score so the near-tie is visible.
