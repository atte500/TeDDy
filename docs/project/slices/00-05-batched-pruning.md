# Slice: Batched Retention Pruning
- **Status:** Planned
- **Milestone:** None (ad-hoc slice)
- **Depends On:** None (independent of slice 00-03, but it protects whatever prefix 00-03 wins)
- **Specs:** None
- **Prototype:** None required
- **Component Docs:** [session_pruning_service.md](/docs/architecture/core/services/session_pruning_service.md)
- **Scope Slug:** `batched-pruning`

## Goal
Make retention pruning fire once every N turns instead of once per turn, so the cached history prefix survives N−1 turns in a row at steady state.

## Context
- `SessionPruningService.prune()` clears its read cache, then calls `_identify_turns_to_prune`, `_apply_retention_limit`, and `_apply_global_budget` in that order.
- `_apply_retention_limit` drops `Turn`-scoped items whose turn id is at or below `max_id - auto_pruning.max_turns_retention` (live value 10).
- History artifacts live in `turn.context` under `Turn` scope, so retention deletes rendered `### Turn N` entries from the front of `## Session History`.
- Measured: mature-session turns 09→13 were strictly append-only, yet one pair collapsed from a 60.2% cacheable prefix to 1.5%, breaking ~4.4KB in right after `### Initial Request`. That is front truncation, and at steady state it fires every turn.
- Settings resolve through `IConfigService.get_setting`, and canonical defaults belong in `ConfigSchema`.
- `_identify_turns_to_prune` implements failure-status pruning and is independent of retention; `_apply_global_budget` runs after retention and is untouched by this slice.

## Scenarios
Primary user journeys and happy paths. These drive End-to-End Acceptance Tests in the Wiring deliverable.

> As a developer running a long session, I want the retained history to change in bursts so the provider can serve the same prefix several turns in a row.

```gherkin
Given `auto_pruning.max_turns_retention: 10` and `auto_pruning.retention_batch: 5`
And a turn context at the retention boundary
When five consecutive turns are planned
Then no turn is pruned for the first four of them
And five turns are pruned together on the fifth
```

```gherkin
Given `auto_pruning.retention_batch: 1`
When a turn crosses the retention boundary
Then exactly one turn is pruned, matching today's cadence
```

## Edge Cases
Boundary conditions, errors, and validation edge cases. These drive granular Unit Tests in Core deliverables.

- **Batch of one:** behaves exactly as today, because the setting must be a safe escape hatch.
- **Batch exceeds available history:** the batch is clamped so at least `max_turns_retention` turns always survive, because pruning more than it keeps would empty the history.
- **Non-positive or unparseable batch:** falls back to `1` with a logged warning, because a bad setting must not silently disable retention.
- **Fewer turns than the threshold:** nothing is pruned and no batch is reserved, because there is no excess to absorb.
- **Sparse turn ids:** a gap in `turn.context` is not counted as a pruned turn, because the batch counter measures ids, not entries.
- **Failure-status pruning active:** its decisions are unchanged, because this slice only touches the retention window.
- **Budget heuristic:** runs after retention with unchanged semantics, because the measured defect is front truncation, not size pressure.

## Key Unknowns

- [x] [Domain] Whether batching is worth the added statefulness. Design Sensitivity: resolved by measurement — front truncation was observed firing once per turn at steady state, so deferring it by N−1 turns is a direct multiplier on prefix reuse; if a future session shows retention firing rarely, the batch simply becomes behaviour-neutral.
- [x] [Harness] Whether batch boundaries are observable without a long real session. Design Sensitivity: resolved; the heuristic operates on `ContextItem` turn ids, so a fixture of N items with sequential ids drives every boundary by construction.

## Impact
1. `[NEW]` `auto_pruning.retention_batch` — new integer setting with a default of `5` and a floor of `1`.
2. `[EXTEND]` `ConfigSchema` — additive typed key with coercion and validation.
3. `[EXTEND]` `SessionPruningService._apply_retention_limit` — accepts the batch size; additive, with `1` preserving current behaviour.
4. `[MIGRATE]` retention tests that assert per-turn cadence.

## Deliverables

- [ ] **Interface** - Add `auto_pruning.retention_batch: 5` to the canonical configuration defaults with integer coercion and a `>= 1` floor.
- [ ] **Harness** - Add a pruning fixture that builds N `ContextItem`s with sequential turn ids, so batch boundaries are observable without a real session.
- [ ] **Wiring** - Read the setting and thread it into `_apply_retention_limit` as `1`, leaving the suite's behaviour identical.
- [ ] **Core** - Implement the batched window: prune only once the excess reaches the batch, then drop the whole batch in one step, clamping so at least `max_turns_retention` turns survive.
- [ ] **Migration** - Update existing retention tests that assert a one-turn deletion per boundary crossing.

## Implementation Notes
The setting is a cadence knob, not a retention length: `max_turns_retention` still defines how much history survives, and the batch only defines how often the excess is collected.

## Verification
1. **Batched cadence:**
   Set `auto_pruning.retention_batch: 5` in `.teddy/config.yaml`, run a session past the retention boundary, and inspect consecutive `input.md` payloads.
   Confirm the rendered `### Turn N` entries disappear in groups of five every fifth turn.
2. **Escape hatch:**
   Set `auto_pruning.retention_batch: 1` and repeat.
   Confirm one turn disappears per boundary crossing, matching the pre-change behaviour.
