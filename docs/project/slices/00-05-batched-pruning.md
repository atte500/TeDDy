# Slice: Batched Retention Pruning
- **Status:** In Progress
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

- [x] **Interface** - Add `auto_pruning.retention_batch: 5` to the canonical configuration defaults with integer coercion and a `>= 1` floor.
- [x] **Harness** - Add a pruning fixture that builds N `ContextItem`s with sequential turn ids, so batch boundaries are observable without a real session.
- [x] **Wiring** - Read the setting and thread it into `_apply_retention_limit` as `1`, leaving the suite's behaviour identical.
- [x] **Core** - Implement the batched window: prune only once the excess reaches the batch, then drop the whole batch in one step, clamping so at least `max_turns_retention` turns survive.
- [ ] **Migration** - Update existing retention tests that assert a one-turn deletion per boundary crossing.

## Implementation Notes
The setting is a cadence knob, not a retention length: `max_turns_retention` still defines how much history survives, and the batch only defines how often the excess is collected.

### Interface
`AutoPruningConfig.retention_batch` is a frozen-dataclass field defaulting to `5`. `_SCHEMA_FIELDS` declares `auto_pruning.retention_batch` as an `int` with an inclusive `minimum=1`, so a clean integer string coerces, `1` is accepted as the escape hatch, and `0` or a negative value raises `ConfigurationError` naming the key. `construct_app_config` already forwards group overrides generically, so no construction branch was needed.

### Harness
`tests/harness/setup/pruning_scenarios.py` is data only, mirroring `context_scenarios.py`. `turn_path(turn_id)` renders `.teddy/sessions/retention-scenario/<NN>/plan.md`, so the production extractor reads the id back unchanged. `turn_context(ids)` builds one selected `Turn`-scoped `ContextItem` per id in the given order, which lets a test express a sparse id gap because retention counts ids rather than entries; `sequential_turn_context(count, start=1)` is the consecutive shorthand. The contract test reads ids through the real `SessionPruningService._extract_turn_id` instead of a duplicated regex, so a change to the path convention breaks the fixture loudly rather than drifting silently.

### Wiring
`prune()` now calls `_apply_retention_limit(items, self._read_retention_batch())`. `_read_retention_batch()` reads `auto_pruning.retention_batch` through `IConfigService`, parses it to an int, and clamps to at least `1`; a missing or unparseable value falls back to `1` so the unit-test config doubles that do not declare the key keep today's cadence. `_apply_retention_limit` consumes the value through an inclusive `retention_batch >= 1` contract assertion, but the window still drops every turn past `max_turns_retention` on each pass, so behaviour is identical to the pre-change cadence. The batched window and the docstring updates that describe it land in the Core deliverable.

The acceptance tracer bullet `tests/suites/acceptance/test_session_pruning_retention_wiring.py` composes a real `YamlConfigAdapter` over a temporary `.teddy/config.yaml` — subclassed only to record every `get_setting` key, so the read stays observable while the real schema path stays intact — plus a real `LocalFileSystemAdapter` (with an `EditSimulator`) rooted in the same temp directory, so the turn files genuinely do not exist and retention runs isolated from failure-status pruning. It drives `SessionPruningService.prune()` and pins both the configuration read and the batch-of-one escape hatch, which stays valid once Core batches the window.

### Core
`_apply_retention_limit` now collects the excess in whole batches. With `excess = max_id - max_turns_retention`, nothing is pruned while `excess < retention_batch`; once the excess reaches the batch, the cut is `threshold = (excess // retention_batch) * retention_batch` and every turn id at or below it is dropped in one pass. Because the cut never passes `excess`, the newest `max_turns_retention` turn positions always survive — the clamp the slice demands — and a batch of one collapses to `threshold = excess`, reproducing the per-turn cadence that predates batching. `max_turns_retention: 10` with `retention_batch: 5` therefore keeps ten through fourteen turns intact and prunes ids 1–5 on the fifteenth, matching the Gherkin primary scenario.

`_read_retention_batch` keeps a missing setting silent (a default of one, so unit-test config doubles that omit the key stay on the old cadence) but logs a module-level warning for a non-positive (`< 1`) or unparseable value before falling back to one, so a bad setting cannot silently disable retention. The module gained a `logger` for that path.

`tests/suites/unit/core/services/test_session_pruning_retention_window.py` drives the outermost `prune()` entry point over `InMemoryConfigService` (a dictionary-backed `IConfigService`) and a `create_autospec` filesystem double whose `path_exists` is always `False`, so failure-status pruning stays inert and only the retention window shapes each result. Sixteen cases cover the batched progression (five counts hold, the fifteenth drops ids 1–5), batch-of-one parity (three counts), both clamp sides (a batch beyond the excess reserves nothing; eight turns at a limit of three drop a batch of five and keep three), a history shorter than the limit, a sparse-id gap (three entries pruned, not eight), and the three bad-batch forms falling back to one with a warning. Red failed on the batching-specific and logged-fallback cases; Green passed all sixteen and the full suite at 2562 passed / 5 skipped.

## Verification
1. **Batched cadence:**
   Set `auto_pruning.retention_batch: 5` in `.teddy/config.yaml`, run a session past the retention boundary, and inspect consecutive `input.md` payloads.
   Confirm the rendered `### Turn N` entries disappear in groups of five every fifth turn.
2. **Escape hatch:**
   Set `auto_pruning.retention_batch: 1` and repeat.
   Confirm one turn disappears per boundary crossing, matching the pre-change behaviour.
