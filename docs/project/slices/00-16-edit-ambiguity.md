# Slice: Ambiguity Detection for Approximate EDIT Matches
- **Status:** In Progress
- **Milestone:** N/A (ad-hoc slice)
- **Depends On:** N/A
- **Specs:** N/A
- **Prototype:** [spikes/prototypes/edit-ambiguity](/spikes/prototypes/edit-ambiguity/)
- **Component Docs:** [EditMatcher](/docs/architecture/core/services/edit_matcher.md), [EditSimulator](/docs/architecture/core/services/edit_simulator.md), [PlanValidator](/docs/architecture/core/services/plan_validator.md)
- **Scope Slug:** `edit-ambiguity`

## Goal
Stop an EDIT from silently landing on the wrong block when the winning FIND match is only approximate and a second candidate is equally plausible, while keeping verbatim matches editable even when a sibling function shares the same body shape.

## Context

- `edit_matcher._refine_and_select_best`: the candidate loop sets `is_ambiguous = True` only when `ratio == best_ratio and ratio > 0 and ratio >= threshold`. A winner at `0.9939` against a runner-up at `0.9879` is accepted silently.
- `edit_matcher.find_best_match`: returns `(match_str, round(score, 2), is_ambiguous, offset)`. The tie comparison runs on the raw ratio while the reported score is rounded to two decimals, so two distinct candidates can both display `0.99`. Disabling the rounding fails exactly one assertion, `test_matcher_rounds_score_to_two_decimal_places`.
- `edit_matcher._apply_indentation_bonus`: promotes a window that matches after `rstrip` with one constant relative indentation offset to exactly `1.0` and returns that offset.
- `edit_matcher._apply_substring_boost`: promotes a verbatim intra-line fragment (single-line FIND) or a literal contiguous multi-line block to `1.0`, and flags ambiguity when the fragment occurs more than once inside the same window.
- `edit_matcher._evaluate_candidates`: scores every seeded window, sorts by the coarse score, then refines only `scored_candidates[:CANDIDATE_EVALUATION_CAP]` (5). The cap is a refinement budget, not a pool filter.
- `edit_matcher_heuristics.gather_candidate_starts`: Tier 1 seeds windows from up to five longest non-blank FIND lines found verbatim in the file; the Tier 2 fuzzy first-line cascade runs only when Tier 1 is empty; Tier 3 scans substrings for a single-line FIND; Tier 4 falls back to exhaustive. On real source with an injected one-character `def` typo, Tier 1 seeded exactly one candidate in all six functions and methods measured.
- `edit_simulator._apply_single_edit`: raises `MultipleMatchesFoundError` when `is_ambiguous and not match_all`, computing `count = content.count(find) if score == 1.0 else 2`. An indentation-only duplicate reports `content.count(find) == 0` while two candidates qualify, so today's message reads "Found 0 ambiguous occurrences". It replaces `best_match` — the real file text — with the REPLACE block, so a tolerated typo cannot corrupt surrounding content.
- `validation_rules/edit.py:_validate_single_edit`: applies the same gate, `is_ambiguous and not match_all and score >= effective_threshold`. Its message carries the path, the two-decimal score, the FIND embed, and a hint — no runner-up and no candidate count.
- `plan.DEFAULT_SIMILARITY_THRESHOLD = 0.95`, applied inclusively. `resolve_similarity_threshold` resolves action params first, then global config, then the default.
- `tests/suites/unit/core/services/test_edit_ambiguity_threshold_gating.py`: deliberately pins the ties-only contract — a tie at or above the threshold is "ambiguous", a tie below it is "could not be located" so the author gets the closest-match diff instead. Its three identical `0.80` windows tie above their own threshold under both the ties-only and refined rules and classify identically, so its assertions hold; only its docstring narrative describes the old contract.

Measured candidate distribution at threshold `0.95`:

| Scenario | Best | Runner-up | Current rule | Refined rule |
| :-- | --: | --: | :-- | :-- |
| Fuzzy near-tie (one-character typo in the target's def line) | 0.9939 | 0.9879 | accept | block |
| Verbatim FIND, near-duplicate sibling | 1.0000 | 0.9939 | accept | accept |
| Verbatim FIND at two locations | 1.0000 | 1.0000 | block | block |
| Indentation-only duplicate | 1.0000 | 1.0000 | block | block |
| Repeating inner lines, one true location | 0.9960 | 0.9237 | accept | accept |
| Tail-duplicate adjacent start | 0.9960 | 0.9237 | accept | accept |
| Def typo on six real functions and methods | 0.9565–0.9994 | 0.0000 | accept | accept (single candidate) |

Swapping a single character in the FIND's `def` line flips which sibling block is edited, with `success` reported at both the simulator and the validator. That is the defect this slice removes.

Three further measurements constrain the design. The refinement cap truncates the reported count without changing any verdict: seeded windows of 7, 40, 8, and 100 all refined to 5, while refine-all cost 19.61 ms against 19.60 ms for 40 small windows, 3.73 ms against 0.78 ms for 100 large windows, and at most +37.89 ms on a 462–1827 ms exhaustive-pool run. The sub-sample filter that gates large blocks never discards a viable window: across the 1571 windows it filtered on a disjoint 1600-line file, the highest true full ratio was `0.0000`. And the full suite stays green under the refined rule, under cap removal, and under both (2196 passed, 5 skipped).

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
- **Indentation-only drift**: If the only difference is a constant relative indentation, then the match is promoted to `1.0` and treated as verbatim, because the REPLACE block is re-indented to the matched offset and indentation-insensitive matching is intentional. Both promoted windows count as candidates even though the authored FIND appears zero times in the file.
- **Tie below the threshold**: If two candidates tie below the effective threshold, then the failure is "could not be located" with the closest-match diff, not an ambiguity error, because there is nothing to disambiguate.
- **Match All requested**: If `Match All: true` is set, then ambiguity never blocks, because the author has declared intent to change every occurrence.
- **Single seeded candidate**: If Tier 1 exact anchoring yields one window, then the refined clause cannot fire, because there is no runner-up above the threshold. Measured on six real functions and methods with an injected `def` typo: `seeded=1`, runner-up `0.0000`, scores `0.9565–0.9994`, all accepted.
- **Duplicate inside one window**: If a single-line FIND occurs twice within the same matched window, then the substring boost keeps reporting ambiguity, because two replacements inside one window are still ambiguous.
- **Shifted start inside one true location**: If a later window start shares most of the true location's lines, then the runner-up stays below the floor. Measured `0.9237` against `0.95` for both a repeating-inner-line block and its tail-duplicate variant, so the edit is accepted.
- **Large-block near-tie**: If two large windows differ only in their first line, then both clear the coarse filter, the cap truncates nothing, and the refined clause blocks the edit exactly as it does for small blocks.
- **Candidate count above five**: Every scored candidate reaches refinement, so the reported count is exact rather than capped at five. Verdicts were identical with and without the cap in every measured scenario.
- **Raw-distinct scores**: The reported score is the raw ratio and is no longer rounded on return, so a distinct winner and runner-up cannot present as an identical two-decimal tie.
- **Large-block exhaustive fallback**: If no FIND line anchors verbatim in a long file, then the exhaustive tier seeds a window per start and the sub-sample filter discards the non-viable ones. Measured: 1571 discarded windows, highest true full ratio `0.0000`.

## Key Unknowns

- [x] [Domain] Carve-out boundary for whitespace-promoted matches: an indentation-only difference is promoted to `1.0`, so a whitespace-drifted match with a `0.98` sibling stays accepted. Resolved: both promotion helpers assign exactly `1.0`, so `top < 1.0` is precisely "no verbatim and no indentation-only match" and is the whole clause. No additional signal is needed.
- [x] [Technical] Shape of the candidate distribution in the matcher contract: widen the existing 4-tuple, or add a sibling function returning a small DTO? Resolved: a six-field `NamedTuple` raises `ValueError: too many values to unpack (expected 4)` at every legacy 4-way site, while a sibling `find_best_match_ex` leaves the 4-tuple intact. The additive seam is chosen, and both legacy entry points derive from one internal decision record.
- [x] [Functional] Message convergence: should the executor and the validator share one ambiguity message builder? Resolved: they share the facts (winner, runner-up, candidate count) and one hint constant, but keep two renderers — the executor emits a single-line exception message and the validator emits structured Markdown with the fenced FIND block. One builder would either flatten the validation detail or bloat the exception.

## Impact

The matcher contract has more than one production consumer, so the change follows the non-breaking expand → migrate → contract sequence.

1. `[EXPAND]` `edit_matcher` — introduce one internal decision record (`match`, raw `score`, `is_ambiguous`, `offset`, `runner_up`, `candidate_count`) and expose it through a new `find_best_match_ex`. `find_best_match` and `find_best_match_and_diff` keep returning their 4-tuples, derived from the same record.
2. `[EXPAND]` `edit_matcher._refine_and_select_best` — apply the refined ambiguity condition so both legacy entry points surface the new verdict without a signature change.
3. `[MIGRATE]` `EditSimulator._apply_single_edit` — read the decision record, raise with the exact candidate count, and drop the hardcoded `else 2`.
4. `[MIGRATE]` `validation_rules/edit.py:_validate_single_edit` — read the decision record and print the runner-up and candidate count at four decimals.
5. `[CONTRACT]` `edit_matcher._evaluate_candidates` — remove `CANDIDATE_EVALUATION_CAP` so every scored candidate reaches refinement.
6. `[CONTRACT]` `edit_matcher.find_best_match` — remove the two-decimal rounding on both return paths, and drop the stale "already rounded" comment in `find_best_match_and_diff`.
7. `[CONTRACT]` `edit_simulator.py` and `validation_rules/edit.py` — delete both local hint literals in favour of one `AMBIGUITY_HINT` constant in `edit_matcher.py`, unified on the "list item `Match All: true`" phrasing.

## Deliverables

- [x] **Interface** - Introduce the matcher's six-field decision record and `find_best_match_ex`, keeping `find_best_match` and `find_best_match_and_diff` on their existing 4-tuples derived from that record.
- [x] **Harness** - Promote the canonical scenarios (verbatim versus near-duplicate sibling, fuzzy near-tie, verbatim duplicate, indentation-only duplicate, repeating-inner-line block) and the N-copy generator into shared test fixtures. The rule, cap, and rounding pytest plugins stay measurement-only.
- [x] **Core** - Implement the refined condition `(ties > 1 and top >= threshold) or (top < 1.0 and second >= threshold)`, and extend the gating module with fuzzy near-tie coverage; its existing assertions hold, so only the docstring narrative changes.
- [x] **Core** - Refine every scored candidate (remove `CANDIDATE_EVALUATION_CAP`) so the reported candidate count is exact.
- [x] **Migration** - `EditSimulator` raises with the exact candidate count from the decision record, imports the shared `AMBIGUITY_HINT`, and loses the hardcoded `else 2`. Update the caller assertion in `tests/suites/integration/adapters/outbound/test_file_system_adapter.py` that pins `Found 2 ambiguous occurrences of 'hello'`.
- [x] **Migration** - `EditActionValidator` prints the similarity score, the runner-up score, and the candidate count at four decimals, and uses the shared `AMBIGUITY_HINT`.
- [x] **Cleanup** - Remove the two-decimal rounding, rewrite `test_matcher_rounds_score_to_two_decimal_places` as `test_matcher_returns_the_raw_similarity_ratio` against the raw-ratio contract, re-point the two decision-record tests as `test_decision_record_and_legacy_adapter_share_the_raw_score` and `test_diff_entry_point_renders_the_diff_below_verbatim`, and drop the stale "already rounded" comment. The empty `spikes/debug/edit-matcher-ambiguity/` directory was already absent.

## Implementation Notes
Every comparison runs on the raw ratio, and the reported score is the raw ratio too, so the ambiguity message can print the winner and runner-up at four decimals.

`_apply_indentation_bonus` and `_apply_substring_boost` both promote to exactly `1.0`, which makes `top < 1.0` precisely mean "no verbatim and no indentation-only match" — the intended carve-out, and the reason the refined clause cannot block a routine edit.

The ambiguity count comes from the candidate set, never from `content.count(find)`. An indentation-promoted duplicate has `content.count(find) == 0` while both windows score `1.0`; the current executor prints "Found 0 ambiguous occurrences" for that case. Switching the wording from "occurrences" to "candidates" also crosses `tests/suites/integration/adapters/outbound/test_file_system_adapter.py`; its fixture `"hello world, hello again"` is a single-line intra-window double, so the truthful count there is `1` and the assertion now pins `Found 1 ambiguous candidate for 'hello'`.

The candidate evaluation cap is retired. While it existed it was a refinement budget, not a pool filter: every seeded window was scored before the top five were sliced, so removing it changed no verdict on any measured path — but it truncated the reported count. Every scored candidate now reaches refinement, so `candidate_count` is exact.

The gating module needs no assertion changes. Its three identical `0.80` windows tie above their own threshold under both the ties-only and refined rules and classify identically; only the module docstring's narrative describes the old contract.

The sub-sample filter is not a recall risk. Above `LARGE_BLOCK_LINE_LIMIT` it discards windows before refinement, but across 1571 discarded windows on a disjoint 1600-line file the highest true full ratio was `0.0000`. Both promotions require every stripped line to match or a literal contiguous block, which the sub-sample already catches.

Tier 1 exact anchoring keeps the blast radius narrow: on real source with an injected typo, every probe seeded a single candidate. The new clause only fires where sibling blocks genuinely share body text; a shifted start inside one true location lands at `0.9237`, below the `0.95` floor.

The simulator replaces `best_match` — the real file text — rather than the FIND string, which is why a tolerated typo cannot corrupt surrounding content and needs no extra guard.

`find_best_match_ex` returns a six-field `NamedTuple` (`match`, `score`, `is_ambiguous`, `offset`, `runner_up`, `candidate_count`). A widened tuple cannot replace the legacy contract: every 4-way unpack site raises `ValueError: too many values to unpack (expected 4)`.

`AMBIGUITY_HINT` lives in `edit_matcher.py`, which both consumers already import. The executor renders a single-line exception message; the validator renders structured Markdown with the fenced FIND block.

The cap-measurement probes (`cap_impact_probe.py`, `cap_worst_case_probe.py`, `cap_exhaustive_pool_probe.py`, `large_block_filter_probe.py`, and `candidate_cap_patch_plugin.py`) import `CANDIDATE_EVALUATION_CAP` and become unrunnable once the cap lands. They stay in the prototype folder as the evidence trail and must not be cited in Verification.

As built, the Interface deliverable put `MatchResult` and `find_best_match_ex` in `edit_matcher.py`, and both `_evaluate_candidates` and `_refine_and_select_best` now return that record, which makes it the single place either legacy entry point reads from. `find_best_match` folds the record back to its four-tuple with `round(result.score, 2)`, and `find_best_match_and_diff` continues to consume `find_best_match`, so the ties-only verdict, the rounding, and the rounded-score diff gate are all unchanged. `test_edit_matcher_decision_record.py` pins the six fields, the raw-versus-rounded split, and the diff gate. Two of its four assertions are intentionally temporary: they describe the legacy adapter that Cleanup rewrites, not the target contract.

As built, the Harness deliverable added `tests/harness/setup/edit_scenarios.py` as a data-only module: it imports nothing from `teddy_executor`, so it cannot couple a test to the matcher it exercises. It exposes `EditScenario` (a `content`/`find` `NamedTuple`), the builders `sibling_function`, `two_sibling_functions`, `fuzzy_find`, `repeated_function`, `duplicate_block_file`, `repeated_line_file`, `fuzzy_repeated_line_find`, `indented_duplicate_file`, `unindented_duplicate_find`, `handler_block_file`, `handler_tail_duplicate_file`, and `fuzzy_handler_find`, and the five canonical bundles `VERBATIM_VS_NEAR_DUPLICATE`, `FUZZY_NEAR_TIE`, `VERBATIM_DUPLICATE`, `INDENTATION_ONLY_DUPLICATE`, and `REPEATING_INNER_LINE`. The fixture text is ported verbatim from `spikes/prototypes/edit-ambiguity/scenarios.py`, so the later deliverables measure the same candidate distributions the probes reported. `tests/suites/unit/test_edit_scenarios_harness.py` holds ten contract tests, pinning each builder's shape and the content/find pairing of every bundle.

Three builders have no consumer yet — `repeated_line_file`, `fuzzy_repeated_line_find`, and `handler_tail_duplicate_file`. They stay because they express the shifted-start-inside-one-true-location and tail-duplicate edge cases recorded in this slice, and re-porting them later would mean re-deriving the same text. The remaining deliverables consume the shared fixtures as follows: Core's refined condition uses `FUZZY_NEAR_TIE` and `VERBATIM_VS_NEAR_DUPLICATE`, Core's cap removal uses `repeated_function`, and the two Migrations use `INDENTATION_ONLY_DUPLICATE` and `VERBATIM_DUPLICATE`.

As built, the refined-rule deliverable reduced the verdict to one disjunction. `_refine_and_select_best` keeps the winning window's intra-window flag from `_apply_substring_boost` in `winner_is_ambiguous` and returns `is_ambiguous = winner_is_ambiguous or _decide_refined_ambiguity(refined_ratios, threshold)`. The helper is a pure function over the refined ratios: it sorts them descending, takes `top` and `second` (with `second = 0.0` when fewer than two candidates exist), counts `ties` at `top`, and returns `(ties > 1 and top >= threshold) or (top < 1.0 and second >= threshold)`; an empty ratio list returns `False`. Because it reads the ratios after both promotions, an indentation-only pair ties at `1.0` and resolves through the tie branch, while the `top < 1.0` branch only fires for a genuinely fuzzy winner. The retired tie-only branch (`ratio == best_ratio and ratio > 0 and ratio >= threshold`) is gone, and the debug branch now prints `len(refined_ratios)` instead of the retired local counter.

`tests/suites/unit/core/services/test_edit_ambiguity_refined_condition.py` adds seven tests over the shared harness fixtures. Three are the behavioral flips that drove the Red: the fuzzy near-tie decision record (`score < 1.0`, `runner_up >= threshold`, `runner_up < score`, `candidate_count == 2`, `is_ambiguous is True`), both legacy entry points surfacing that verdict with an empty diff, and the validator reporting a single ambiguity error naming the FIND block. Four are carve-out guards that already passed and must keep passing: a verbatim winner beside a near-duplicate sibling stays accepted, the indentation-promoted duplicate stays ambiguous, a single true location with a shifted start stays accepted with its runner-up below the floor, and `Match All` bypasses the verdict entirely.

`test_edit_ambiguity_threshold_gating.py` received only its module docstring, rewritten to describe the refined contract. Its assertions are untouched and still pass: the three identical `0.80` windows tie at the same ratio and classify identically under the tie-only and refined rules, so they keep pinning threshold gating rather than rule shape. The full suite ended at 2229 passed, 5 skipped.

As built, the cap-removal deliverable confined the change to `_evaluate_candidates`. Every scored candidate now reaches `_refine_and_select_best` through `candidates_to_refine = scored_candidates or [(0.0, file_lines[:num_find_lines])]`; the `scored_candidates[:CANDIDATE_EVALUATION_CAP]` slice and the `CANDIDATE_EVALUATION_CAP = 5` constant are gone, and the docstring reads "Evaluates every candidate, sub-sampling the ratio for large blocks." Two parts of the function are deliberately kept: the coarse-score sort, because it preserves the winner tie-break when two distinct windows promote to the same refined ratio, and the empty-pool fallback, because it seeds the whole-file window when no candidate was scored. `_refine_and_select_best` needed no change — it already derived `runner_up` and `candidate_count` from `refined_ratios`, so the record became truthful the moment the pool stopped truncating.

`tests/suites/unit/core/services/test_edit_matcher_candidate_count.py` adds three tests over the shared `repeated_function` and `sibling_function` fixtures. The parametrized count test at 7 and 12 copies pins `candidate_count == copies` for a def-typo FIND, plus a sub-verbatim `score`, a runner-up equal to the score, and `is_ambiguous is True`; it is the test that flipped `assert 5 == 7` and `assert 5 == 12` in the Red. The winner-text guard pins `record.match == sibling_function("compute")`, proving refinement still returns the real file block rather than the typo'd FIND.

The cap-measurement probes (`cap_impact_probe.py`, `cap_worst_case_probe.py`, `cap_exhaustive_pool_probe.py`, `large_block_filter_probe.py`, and `candidate_cap_patch_plugin.py`) import `CANDIDATE_EVALUATION_CAP` and are now unrunnable. They stay in the prototype folder as the evidence trail and must not be cited in Verification; the six Verification-cited probes import only `find_best_match` and `_apply_single_edit` through `rule_harness`, so they remain runnable. The full suite ended at 2232 passed, 5 skipped.

As built, the simulator-migration deliverable rewrote `EditSimulator._apply_single_edit` to call `find_best_match_ex` and raise with `result.candidate_count`, pluralizing the noun (`candidate`/`candidates`) because a single-candidate window is reachable, and appending the shared `AMBIGUITY_HINT`. The new constant lives in `edit_matcher.py`, unified on the list-item `Match All: true` phrasing, and both the hardcoded `else 2` and the local hint literal are gone. The simulator now gates on the raw score from `find_best_match_ex` rather than the rounded score `find_best_match` returned, which matches the matcher's own raw comparisons; the not-found message keeps its `: .2f` format spec so the display is unchanged. Cleanup still strips the rounding from `find_best_match` itself.

The integration fixture `"hello world, hello again"` turned out to be a single-line intra-window double: the substring boost promotes its one window to `1.0` and flags it, so the record reports `candidate_count=1` and `runner_up=0.0`, and the assertion now pins `Found 1 ambiguous candidate for 'hello'`. The earlier note claiming only the wording crosses that test was corrected accordingly.

`tests/suites/unit/core/services/test_edit_simulator.py` adds a parameterized count test over `INDENTATION_ONLY_DUPLICATE` and `VERBATIM_DUPLICATE`, both genuine two-window scenarios, pinning `Found 2 ambiguous candidates`. The indentation case is the sharp one: `content.count(find) == 0` while both windows score `1.0`, so the old count path printed `Found 0`. The full suite ended at 2234 passed, 5 skipped.

As built, the validator-migration deliverable composes the ambiguity message inside the existing `is_ambiguous and not match_all and score >= effective_threshold` branch of `_validate_single_edit` from a second `find_best_match_ex` call: `**Similarity Score:**` and `**Runner-up Score:**` render at `:.4f`, `**Candidates Above Threshold:**` is the plain integer `record.candidate_count`, and `**Hint:**` carries the shared `AMBIGUITY_HINT`. The gate itself is unchanged — `find_best_match_and_diff` and its raw score still decide whether the branch runs — and the not-found branch keeps its two-decimal rendering and closest-match diff, so `find_best_match`'s own rounding stays Cleanup's job. The second matcher call is the deliberate minimal move: `find_best_match_and_diff` folds the record back to its four-tuple, and the not-found diff still needs it.

`test_validator_reports_the_fuzzy_near_tie_as_ambiguous` gained four assertions measured from the record — `**Similarity Score:** 0.9939`, `**Runner-up Score:** 0.9879`, `**Candidates Above Threshold:** 2`, and the `AMBIGUITY_HINT` presence — plus the import of the shared constant so the assertion reads the single source of truth. One acceptance pin trailed the retired hint tail: `test_edit_transparency_and_bulk.py::test_edit_ambiguity_hint_update` asserted the old backtick phrasing, so it now imports `AMBIGUITY_HINT` from the matcher and asserts against it. That failure was classified as a Local Flaw, not a systemic regression, because the production change was green and only the assertion trailed the retired wording. The full suite ended at 2234 passed, 5 skipped.

As built, the Cleanup deliverable removed the rounding from `find_best_match`, which now returns `result.score` directly, and dropped the stale "already rounded" comment from `find_best_match_and_diff`. Three assertions were re-pointed at the raw contract: `test_matcher_rounds_score_to_two_decimal_places` became `test_matcher_returns_the_raw_similarity_ratio` and pins `36/38`; `test_decision_record_keeps_raw_score_while_legacy_adapter_rounds` became `test_decision_record_and_legacy_adapter_share_the_raw_score` and asserts the adapter and record carry the identical raw float; `test_diff_entry_point_gates_the_diff_on_the_rounded_score` became `test_diff_entry_point_renders_the_diff_below_verbatim` and pins `798/801` with a non-empty diff, because the raw ratio `0.9962547` now falls inside the `0 < score < 1.0` diff gate that the rounding previously suppressed. The gate itself needed no change. Both acceptance pins are display-only: `1.00, 0.86` and `0.84` render identically from raw scores. `spikes/debug/edit-matcher-ambiguity/` was already absent, so nothing was deleted. The full suite ended at 2234 passed, 5 skipped.

## Verification

1. **Fuzzy near-tie is blocked:**
   Run `uv run python spikes/prototypes/edit-ambiguity/near_tie_probe.py`.
   Verify both `near_tie_closer_to_alpha` and `near_tie_closer_to_beta` report `ambiguous=True` and the validator classification `ambiguous`.
2. **Verbatim match stays editable:**
   Run `uv run python spikes/prototypes/edit-ambiguity/ambiguity_rule_verdict_probe.py`.
   Verify `verbatim_vs_near_duplicate` reports `refined: accepted` while `fuzzy_near_tie` reports `refined: AMBIGUOUS`.
3. **Candidate count is truthful:**
   Run `uv run python spikes/prototypes/edit-ambiguity/ambiguity_rule_probe.py`.
   Verify `copies=2`, `3`, `5`, and `7` report `refined_candidates` equal to the copy count and that the executor message carries that same number, never `Found 0` and never a fixed `2`.
4. **Indentation-promoted duplicates count from the candidate set:**
   Run `uv run python spikes/prototypes/edit-ambiguity/overlap_and_count_probe.py`.
   Verify `indentation_only_duplicate` reports `candidates=2 count_find=0` and its executor message reports 2 candidates.
5. **Real source is unaffected:**
   Run `uv run python spikes/prototypes/edit-ambiguity/real_source_probe.py`.
   Verify every line reports `refined=accepted seeded=1`, with def-typo scores between `0.9565` and `0.9994`.
6. **Ambiguity message reads correctly in the review pane:**
   Run `uv run python spikes/prototypes/edit-ambiguity/message_preview_probe.py --precision 4`.
   Verify the validator and executor messages print the winning score, the runner-up score, and the candidate count.
   Then author a plan whose `EDIT` targets one of two sibling functions, with a one-character typo in the target function's `def` line, start a session, and open the plan review pane on that turn.
   Confirm the `EDIT` node is flagged and shows the runner-up beside the winning score so the near-tie is visible.
