# Slice: Retention Ceiling

- **Status:** In Progress
- **Milestone:** None (ad-hoc)
- **Depends On:** [Batched Retention Pruning](00-05-batched-pruning.md)
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [session_pruning_service.md](/docs/architecture/core/services/session_pruning_service.md)
- **Scope Slug:** `retention-ceiling`

## Goal
Make `auto_pruning.max_turns_retention` mean what its name says: a hard ceiling on how many turns the turn-scoped history may hold, with `auto_pruning.retention_batch` defining how many turns are dropped together once that ceiling is exceeded. The user pays a bounded context cost and the config comment stops lying.

## Context
- `SessionPruningService._apply_retention_limit`: before this slice computed `excess = max_id - limit`, returned unchanged while `excess < retention_batch`, then cut every id at or below `(excess // retention_batch) * retention_batch`. `max_turns_retention` therefore behaved as a floor: with the shipped `10`/`5` the live window oscillated between 10 and 14 turns, and the bundled comment "Max historical turns retained in turn context" was false at the peak.
- `SessionPruningService.prune`: runs failure-status pruning first, then the retention window, then the global token budget — every session turn. Only the retention window is batched; the other two fire immediately and are untouched by this slice.
- `_map_turn_ids`: already returns a `{item index → turn id}` map plus the maximum id, and `_extract_turn_id` already normalizes link-aware paths, so no new path parsing is needed.
- `ContextItem`: carries `selected` and `auto_prune_reason`, so a turn is deselected by writing `selected=False` with a reason and stays visible in the reviewer context pane as the audit trail.
- `config.yaml`: ships `max_turns_retention: 10` and `retention_batch: 5`, so the current peak is 14 turns against a key claiming a maximum of 10.
- Settled with the user during alignment: keep the key name rather than rename it, because a renamed key reads as `0` through `get_setting` and `limit <= 0` returns the items untouched, which would silently disable retention for every existing `.teddy/config.yaml`.
- Settled during drafting: the ceiling cannot be an id-based cutoff recomputed on every turn, because the recomputed cutoff advances by one id per turn and would drop exactly one turn per turn, reintroducing the prefix-cache churn that batching exists to remove. The rule counts the distinct turn ids still selected and keeps only the newest `max(1, limit - retention_batch + 1)` of them, which is idempotent across repeated `prune()` calls and indifferent to id contiguity.

## Scenarios

> As a TeDDy user running long sessions, I want the turn-scoped history to never exceed my configured ceiling, so that context cost stays bounded and the setting name tells the truth.

```gherkin
Given auto_pruning.max_turns_retention is 10 and auto_pruning.retention_batch is 5
And the turn context holds selected turn ids 1 through 10
When turn id 11 enters the turn context
Then turn ids 1 through 5 are deselected together with the reason "Turn exceeds retention limit of 10"
And the selected history holds turn ids 6 through 11
```

```gherkin
Given the selected history holds turn ids 6 through 11 after a batch drop
When turn ids 12, 13, 14 and 15 enter the turn context
Then no turn is deselected by retention
And the selected history never exceeds ten turns
```

```gherkin
Given auto_pruning.max_turns_retention is 10 and auto_pruning.retention_batch is 1
And the turn context holds selected turn ids 1 through 10
When turn id 11 enters the turn context
Then exactly turn id 1 is deselected
And each further turn id deselects exactly one more turn
```

## Edge Cases
- **History shorter than the ceiling**: if the selected history holds fewer turns than `max_turns_retention`, nothing is deselected, because there is no excess to bound.
- **Exactly at the ceiling**: if the selected history holds exactly `max_turns_retention` turns, nothing is deselected, because the ceiling is inclusive.
- **Overage of one**: at ten turns retained with a batch of five, one extra turn drops five turns and leaves six, because the trigger is the ceiling and the drop is a whole batch.
- **Overage larger than the batch**: the drop is the overage plus a full batch minus one, so the post-prune window always lands on the trough instead of parking above it.
- **Batch of one**: `max(1, limit - 1 + 1)` keeps the newest `limit` turns, which reproduces the per-turn cadence that predates batching.
- **Batch at or above the ceiling**: the retained count clamps to `max(1, ...)`, so at least the newest turn always survives; retention must never empty the history.
- **Sparse turn ids**: the count is the number of distinct selected turn ids, so a gap neither counts as a pruned turn nor inflates the ceiling, and the newest positions still survive.
- **Turn deselected by another heuristic**: a turn whose items are all deselected by failure-status pruning does not occupy context, so it does not count against the ceiling and must not be re-annotated with a retention reason.
- **Repeated pruning**: running the window twice over the same context deselects nothing the second time, because the post-prune count already sits at or below the ceiling.
- **Newest turn safety**: the retained set is the newest ids, so the turn currently executing is never deselected.
- **Retention disabled**: `max_turns_retention` at zero or below returns the items untouched, unchanged from today.
- **Unparseable batch**: a non-positive or unparseable `retention_batch` still falls back to one with a warning, unchanged from today.

## Key Unknowns
None. The domain rule was settled with the user during alignment, the batch fallback and disable behaviour are unchanged, the change touches no external system or user-facing interaction, and no scenario is gated on ambient runtime state. The retention-window cases are already expressible with the existing `turn_context(ids)` and `sequential_turn_context(count, start=1)` builders, so no harness unknown remains.

## Impact
1. `[EXTEND]` `SessionPruningService._apply_retention_limit` — rule inverted from an id-based floor with batching to a selected-count ceiling with batching; signature and call site unchanged, so `prune()` needs no edit.
2. `[MIGRATE]` Prose stating the retention promise — `src/teddy_executor/resources/config/config.yaml` (both comments), `docs/architecture/core/services/session_pruning_service.md` (retention bullet and sparing context), `docs/architecture/core/domain/config_schema.md` (`AutoPruningConfig` contract), `docs/architecture/core/ports/outbound/config_service.md` (key table), and one addendum line in `docs/project/slices/00-05-batched-pruning.md` recording that this slice supersedes its window arithmetic.
3. `[MIGRATE]` Retention tests — `tests/suites/unit/core/services/test_session_pruning_retention_window.py` and `tests/suites/acceptance/test_session_pruning_retention_wiring.py` re-pinned to the ceiling band.
4. `[PRUNE]` The below-batch guard and the floor wording in the `_apply_retention_limit` docstring, once the ceiling rule replaces them.

## Deliverables
- [x] **Wiring** - Re-pin the acceptance tracer bullet `tests/suites/acceptance/test_session_pruning_retention_wiring.py` to the ceiling promise, keeping its real `YamlConfigAdapter` over a temporary `.teddy/config.yaml` and its real `LocalFileSystemAdapter` so the configuration read stays observable end to end, and asserting both a batched drop and the batch-of-one cadence through the outer `prune()` entry point.
- [x] **Core** - Extend the ceiling's coverage and finish its prose. The rule itself shipped with Wiring (see Implementation Notes) so every commit stayed green: `_apply_retention_limit` counts the distinct turn ids that still hold a selected item, returns unchanged at or below `max_turns_retention`, and otherwise keeps only the newest `max(1, max_turns_retention - retention_batch + 1)`. Remaining here: add the granular edge-case cases (repeated pruning is a no-op, exactly-at-the-ceiling, an overage larger than the batch stated as its own case, retention disabled, and the bad-batch fallback alongside the migrated band), settle the final docstring, and align every prose surface listed under Impact.
- [x] **Cleanup** - Prune the two hygiene findings from the Verification audit. Remove the unreachable `retention_batch: int = 1` default from `_apply_retention_limit`, because its only caller always passes `_read_retention_batch()`, which clamps to at least one; fold `test_history_shorter_than_the_retention_limit_is_untouched` into the short-count end of the `test_history_at_or_under_the_ceiling_is_untouched` parametrization, because both drive the same return-untouched branch with no invariant variation; then confirm the full suite stays green at seventeen retention cases.

## Implementation Notes
The ceiling and the floor prune on the same cadence — one batch every `retention_batch` turns — so the prefix-cache benefit is identical between the two designs. What changes is which promise the setting makes and how deep the retained history runs: the ceiling's trough is `limit - batch + 1` turns rather than `limit`, so at the shipped defaults the number of turns held between collections falls from 10 to 6, and anyone who wants the old depth at the old cadence sets `max_turns_retention` to `14` to keep a guaranteed ten.

Pruning is evaluated against the turn ids present in the gathered context, so the first drop lands on the turn after the ceiling is first exceeded, not on the turn that reaches it. Slices and tests should be phrased by the ids in the context rather than by "when turn N starts", to stay free of that off-by-one.

### Wiring
The tracer bullet drives the outer `prune()` entry point over a real `YamlConfigAdapter` — subclassed only to record every `get_setting` key — and a real `LocalFileSystemAdapter` rooted in the same temporary directory, so both retention settings are read from a genuine `.teddy/config.yaml` while no turn artifact exists on disk to trigger failure-status pruning. `_prune_with(tmp_path, *, limit, batch, turn_count)` composes that boundary once and returns the pruned context together with the recorder, so both scenarios share one composition instead of duplicating adapter wiring.

The acceptance assertion cannot pass without the arithmetic changing, and the change contradicts five pre-existing floor-semantics unit cases, so the rule inversion landed in this commit rather than in Core: the per-deliverable gate requires every commit to be green. `_apply_retention_limit` now counts the distinct turn ids that still hold a selected item, returns the items untouched at or below `max_turns_retention`, and otherwise keeps the newest `max(1, limit - retention_batch + 1)` ids while annotating every dropped turn with `Turn exceeds retention limit of N`. Skipping items that are already deselected keeps a turn removed by failure-status pruning free of a retention reason. `_map_turn_ids` lost its `max_id` return, which had no other caller.

The shipped numbers are the band itself: `limit=4, batch=2` over five turns retains `4 - 2 + 1 = 3` ids and drops 1–2; a batch of one retains four and drops only id 1; and the primary Gherkin falls out as eleven turns against `10`/`5` keeping the newest six. The five migrated unit cases were re-pinned to that band — at or under the ceiling holds, the first turn past the ceiling drops a full batch, a batch beyond the ceiling clamps to the newest turn, an overage larger than the batch lands on the trough, and a sparse id gap counts distinct turns rather than path ids. The batch-of-one, short-history, and bad-batch cases needed no edit. Targeted runs: 22 passed for the acceptance module plus both retention unit modules, 11 passed for the pruning sweep across the acceptance and integration suites, and the full suite at 2581 passed / 5 skipped.

### Core
The coverage audit came first, because the committed module already carried most of the slice's edge cases after the Wiring migration. At-or-under the ceiling is covered by the parametrized `[8, 9, 10]`, which keeps the exactly-at-the-ceiling case inside that parametrization rather than duplicating it as a fourth identical test; the first turn past the ceiling, batch-of-one parity, the clamp when the batch meets or exceeds the ceiling, an overage larger than the batch, a short history, a sparse id gap, and all three bad-batch forms with a logged warning were already covered. Three invariants were genuinely missing, and all three passed on first run: this deliverable characterizes a rule that shipped with Wiring rather than changing behaviour. `test_retention_disabled_leaves_every_turn_selected` pins that a ceiling of zero returns a twelve-turn history untouched, because the disable path returns before the band arithmetic. `test_pruning_twice_deselects_nothing_further` pins idempotency: a second pass over the first pass's result changes no `selected` flag and no reason, because the post-prune count already sits on the trough. `test_a_turn_already_deselected_keeps_its_reason_and_the_newest_six` is the sharpest, pinning two invariants at once — a turn dropped by another heuristic holds no context, so it neither counts against the ceiling nor earns a retention reason, and the reason it already carries survives. It builds the pre-deselected item with `dataclasses.replace`, so `ContextItem` needed no change. The module went from fourteen to seventeen cases.

The prose work was surgical, driven by the verbatim wording captured during orientation. `_read_retention_batch` now names the batch as the drop size past the ceiling and states that it never sets the retained depth. The two bundled `config.yaml` comments became "Ceiling on historical turns held in turn context" and "Oldest turns dropped together once the ceiling is exceeded (1 = per-turn cadence)", so the shipped file no longer claims a maximum it violates at the peak. The pruning component doc renamed its heuristic to a retention ceiling in the purpose line and the heuristic order, and its bullet now states the band: nothing is deselected at or below the ceiling, past it only the newest `max(1, max_turns_retention - retention_batch + 1)` survive, the retained count never falls below one turn, and a batch of one keeps the newest `max_turns_retention`. The schema doc's `AutoPruningConfig` contract names both keys by role, ceiling and drop size, and the port key table gives `max_turns_retention` its default of `10` plus its ceiling semantics while `retention_batch` carries its default, floor, and drop-size role.

Slice 00-05 gained a forward-pointing note rather than a rewrite: its recorded floor arithmetic stays as the truthful history of what was built then, and the note states that this slice supersedes it, that the batch cadence is unchanged, and that the retained depth is now `max_turns_retention - retention_batch + 1` turns.

The pruning reason string stays `Turn exceeds retention limit of N`, because the slice's Gherkin pins that exact wording; "ceiling" names the setting's promise, while the reason names the limit the turn exceeded. Targeted run: 78 passed across the retention unit module (17), the acceptance tracer bullet (2), and the config-schema module. Full suite: 2584 passed / 5 skipped, the Wiring baseline plus the three new cases.

### Verification Audit
Three audits ran before completion. The production-double audit found no skeleton value, placeholder, or hardcoded outcome in `SessionPruningService`: every retained or dropped turn derives from configuration and the gathered `ContextItem` ids. The upstream/downstream audit confirmed `_apply_retention_limit` has exactly one caller — `prune()` — and that no surface besides the pruning service reads `auto_pruning.max_turns_retention`; `test_session_pruning_service_refinement.py` declares a ceiling of `25` against one-to-three-turn contexts, where the window returns before any arithmetic. The harness audit confirmed both retention modules build their turns through `tests.harness.setup.pruning_scenarios` rather than inline `ContextItem` construction.

Two slice-scoped hygiene findings became this Cleanup deliverable. First, `_apply_retention_limit` still declares `retention_batch: int = 1`. That default was correct when slice 00-05 introduced it, because `prune()` then threaded a literal one, but `prune()` now always passes `_read_retention_batch()`, which clamps to at least one, so the default is unreachable — and DI purity forbids an unreachable concrete default in shipped code. Second, `test_history_shorter_than_the_retention_limit_is_untouched` and the parametrized `test_history_at_or_under_the_ceiling_is_untouched` drive the identical return-untouched branch with only the count differing, so the fix widens the parametrization to a short count and deletes the standalone case, keeping seventeen cases across one fewer test function.

### Cleanup
`_apply_retention_limit` now declares `retention_batch: int` with no default. The default was introduced by slice 00-05, when `prune()` threaded a literal `1`, and became unreachable once `prune()` started passing `_read_retention_batch()` — which returns at least one by construction, falling back from a missing, non-positive, or unparseable setting. Removing it makes the batch a required argument, so a future caller must state the cadence explicitly, and the `assert retention_batch >= 1` guard keeps the invariant visible at the boundary.

The consolidation widened `test_history_at_or_under_the_ceiling_is_untouched` to `[3, 8, 9, 10]` and deleted the standalone short-history case. Both drove the identical return-untouched branch with only the count differing, so the three-turn history remains exercised without a second function; the parametrization's docstring moved with it, from "a history that never exceeds ten turns" to naming the short history explicitly. The two edits offset each other on the module's case count, and the acceptance module was untouched.

Suite parity is the evidence this deliverable has: the retention module reported 17 passed, and the full unfiltered suite reported 2584 passed / 5 skipped, both unchanged from the committed baseline. Cleanup adds no test by definition, so identical counts across one fewer test function and one stricter signature is exactly the outcome that proves no exercised case and no caller relied on what was removed.

## Verification
1. **Ceiling drops a whole batch:**
   Set `auto_pruning.max_turns_retention: 4` and `auto_pruning.retention_batch: 2` in `.teddy/config.yaml`.
   Run `teddy resume -m "continue"` repeatedly until at least five turn ids exist, then start one more turn and open the plan reviewer.
   Verify the context pane lists the two oldest turns as unselected with `Turn exceeds retention limit of 4`, and the three newest turns as selected.
2. **Batch of one keeps the old cadence:**
   Change `auto_pruning.retention_batch` to `1` and run another turn.
   Verify exactly one additional turn becomes unselected, and the selected history holds four turns.
3. **Restore defaults:**
   Remove the two overrides from `.teddy/config.yaml` and confirm the plan reviewer no longer marks any turn for retention while the session is under ten turns.
