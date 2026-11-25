# Slice: Retention Ceiling

- **Status:** Planned
- **Milestone:** None (ad-hoc)
- **Depends On:** [Batched Retention Pruning](00-05-batched-pruning.md)
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [session_pruning_service.md](/docs/architecture/core/services/session_pruning_service.md)
- **Scope Slug:** `retention-ceiling`

## Goal
Make `auto_pruning.max_turns_retention` mean what its name says: a hard ceiling on how many turns the turn-scoped history may hold, with `auto_pruning.retention_batch` defining how many turns are dropped together once that ceiling is exceeded. The user pays a bounded context cost and the config comment stops lying.

## Context
- `SessionPruningService._apply_retention_limit`: today computes `excess = max_id - limit`, returns unchanged while `excess < retention_batch`, then cuts every id at or below `(excess // retention_batch) * retention_batch`. `max_turns_retention` therefore behaves as a floor: with the shipped `10`/`5` the live window oscillates between 10 and 14 turns, and the bundled comment "Max historical turns retained in turn context" is false at the peak.
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
- [ ] **Wiring** - Re-pin the acceptance tracer bullet `tests/suites/acceptance/test_session_pruning_retention_wiring.py` to the ceiling promise, keeping its real `YamlConfigAdapter` over a temporary `.teddy/config.yaml` and its real `LocalFileSystemAdapter` so the configuration read stays observable end to end, and asserting both a batched drop and the batch-of-one cadence through the outer `prune()` entry point.
- [ ] **Core** - Implement the ceiling in `_apply_retention_limit`: count the distinct turn ids that still have a selected item, return unchanged at or below `max_turns_retention`, otherwise deselect every selected turn id older than the newest `max(1, max_turns_retention - retention_batch + 1)` and annotate them with the retention reason. Update the docstring, invert the sixteen cases in `test_session_pruning_retention_window.py` to the `[limit - batch + 1, limit]` band while keeping batch-of-one parity, the sparse-id case, the disable case, and the bad-batch fallback, and align every prose surface listed under Impact.

## Implementation Notes
The ceiling and the floor prune on the same cadence — one batch every `retention_batch` turns — so the prefix-cache benefit is identical between the two designs. What changes is which promise the setting makes and how deep the retained history runs: the ceiling's trough is `limit - batch + 1` turns rather than `limit`, so at the shipped defaults the number of turns held between collections falls from 10 to 6, and anyone who wants the old depth at the old cadence sets `max_turns_retention` to `14` to keep a guaranteed ten.

Pruning is evaluated against the turn ids present in the gathered context, so the first drop lands on the turn after the ceiling is first exceeded, not on the turn that reaches it. Slices and tests should be phrased by the ids in the context rather than by "when turn N starts", to stay free of that off-by-one.

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
