# Slice: Deprecate global_context_threshold Backward Compatibility
- **Status:** In Progress
- **Type:** Cleanup
- **Milestone:** [Milestone 2: Stability & Infrastructure](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [Stability & Bug Fixes](/docs/project/specs/stability-and-bugfixes.md)
- **Component Docs:** [ConfigService](/docs/architecture/core/ports/outbound/config_service.md), [SessionPruningService](/docs/architecture/core/services/session_pruning_service.md)

## Business Goal
Remove the backward compatibility fallback for the deprecated `global_context_threshold` config key. The rename to `turn_context_threshold` has been complete since slice 02-07, and the fallback is now dead code that should be eliminated to prevent confusion and reduce maintenance burden.

## Scenarios
> As a maintainer, I want to remove the `global_context_threshold` fallback so that the codebase only uses the canonical `turn_context_threshold` key.

```gherkin
Given the config.yaml has only auto_pruning.turn_context_threshold = 20000
When the pruning service checks the threshold
Then it should use the value 20000
And it should NOT fall back to any deprecated key
```

## Edge Cases
- **Existing configs with old key**: Users who still have `global_context_threshold` in their `config.yaml` will silently get the default value (0 = skip pruning). This is acceptable since the deprecation period has been long enough and the migration path was clearly documented.
- **Zero threshold**: If `turn_context_threshold` is 0 or negative, the global budget heuristic should be skipped (existing behavior preserved).

## Implementation Notes
- **Seam (02-15-001)**: Removed backward compatibility fallback from `_get_turn_context_threshold()` in `session_pruning_service.py`. The method now only reads `auto_pruning.turn_context_threshold`. If not set, returns 0 (skip budget heuristic). Removed `import logging` as the deprecation warning was the only use.
- **Cleanup (02-15-002)**: The backward compatibility test `test_backward_compatibility_global_context_threshold_still_works` was removed during Integration Local Recovery (the test expected the old fallback behavior that was intentionally removed). Absorbed into the Seam deliverable.
- **New Test**: Added `test_turn_context_threshold_no_longer_falls_back` to assert that when only `global_context_threshold` is set (old key) and `turn_context_threshold` is None, the pruning service treats it as unset (threshold 0 → no pruning). This test passes.
- **Integration**: Full suite (804 tests) passes with 0 failures after the changes.
- **Cleanup (02-15-003)**: Updated `config_service.md` to remove the two deprecated `global_context_threshold` references: stripped the "Falls back to `auto_pruning.global_context_threshold`" suffix from the `turn_context_threshold` entry and deleted the entire `global_context_threshold` entry. Full suite (815 tests) passes with 0 failures after the changes.
- **Cleanup (02-15-004)**: Updated `session_pruning_service.md` to remove three deprecated references: (1) deleted the "Stale Config Key" failure mode bullet entirely, (2) removed the fallback reference from the Outbound port description, (3) simplified the Backward Compatibility section to only mention the sole key `turn_context_threshold`. Fixed a duplicate line bug in the Backward Compatibility section. Full suite (815 tests) passes with 0 failures after the changes.

## Deliverables
- [x] **Seam** - Remove backward compatibility fallback from `_get_turn_context_threshold()` in `session_pruning_service.py`: remove the try/except fallback to `global_context_threshold`, simplify to read only `turn_context_threshold`.
- [x] **Cleanup** - Remove backward compatibility test `test_backward_compatibility_global_context_threshold_still_works` from `test_session_pruning_service_refinement.py` (absorbed into Seam deliverable during Integration Local Recovery).
- [x] **Cleanup** - Update `config_service.md` architecture doc to remove the deprecated key reference.
- [x] **Cleanup** - Update `session_pruning_service.md` architecture doc to remove fallback key references.
- [ ] **Cleanup** - Update `02-stability-and-polish.md` milestone doc to remove the backward compatibility note.
- [ ] **Wiring** - Run full test suite to confirm no regressions.
