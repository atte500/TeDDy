# Slice: 02-07-Pruning Refinement

- **Status:** In Progress
- **Type:** Refactor
- **Milestone:** [docs/project/milestones/02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [docs/project/specs/stability-and-bugfixes.md](/docs/project/specs/stability-and-bugfixes.md)
- **Component Docs:** [docs/architecture/core/services/session_pruning_service.md](/docs/architecture/core/services/session_pruning_service.md)

## Business Goal
Correct the `global_context_threshold` auto-pruning logic to sum ONLY files from `turn.context` (Turn scope), excluding `session.context` (Session scope) and system prompts (System scope), as specified. Also rename the configuration key to `turn_context_threshold` for semantic accuracy.

## Scenarios
> As a session user, I want the pruning threshold to only consider Turn-scope files so that session-scope and system prompt tokens do not trigger premature pruning of files in the working set.
```gherkin
Given a ProjectContext with:
  - 3 Turn-scope items (total 10k tokens)
  - 5 Session-scope items (total 40k tokens)
  - 1 System prompt (2k tokens)
  - global_context_threshold = 15k
When prune() is called
Then only Turn-scope items should be summed (10k <= 15k → no pruning)
And the system prompt token count should NOT be added to the sum
And no files should be pruned
```

> As a session user, I want to use the new `turn_context_threshold` config key so that the configuration matches the actual behavior.
```gherkin
Given the config.yaml has auto_pruning.turn_context_threshold = 20000
And the ProjectContext has:
  - 3 Turn-scope items (total 25k tokens)
When prune() is called
Then the largest Turn-scope file should be pruned
And the old global_context_threshold key should NOT be read
```

## Edge Cases
- **Backward Compatibility**: If a user has an existing config.yaml with `global_context_threshold`, the system must still read that key and use its value, but log a deprecation warning.
- **Zero Threshold**: If `turn_context_threshold` is set to 0 or negative, the global budget heuristic should be skipped entirely (same as current behavior with `global_context_threshold: 0`).
- **Only Session-Scope Items**: If there are no Turn-scope items in the context, the threshold check should be a no-op (0 <= threshold → no pruning).
- **system_prompt_tokens Still Passed**: After removing `system_prompt_tokens` from the method signature, callers that still pass it (e.g., tests) will break. Migration must update all callers.

## Deliverables
- [x] **Contract** - Rename `auto_pruning.global_context_threshold` to `auto_pruning.turn_context_threshold` in bundled `config.yaml`.
- [ ] **Contract** - Remove `system_prompt_tokens: int = 0` parameter from `_apply_global_budget` signature.
- [ ] **Harness** - Update all test fixtures and test files that reference `global_context_threshold` to use `turn_context_threshold`.
- [ ] **Harness** - Update all test callers of `_apply_global_budget` to remove `system_prompt_tokens` argument.
- [ ] **Seam** - Add backward compatibility in pruning service: fallback to `global_context_threshold` if `turn_context_threshold` is not set, with a deprecation log.
- [ ] **Logic** - Refactor `_apply_global_budget` to:
  1. Read `turn_context_threshold` (with backward compatibility fallback).
  2. Sum only items with `scope == "Turn"` for the threshold check.
  3. Remove `system_prompt_tokens` usage from the sum.
  4. Remove `system_prompt_tokens` parameter.
  5. Update the call site in `prune()` to not pass `system_prompt_tokens`.
- [ ] **Migration** - Update `session_orchestrator.py` and `context_service.py` if they pass `system_prompt_tokens` to `prune()` (they do not directly — the pruning service extracts it from `context.system_prompt_tokens` itself, so no changes needed at those callers except removing the local variable and extraction logic).
- [ ] **Cleanup** - Update documentation references in:
  - `docs/project/specs/stability-and-bugfixes.md`
  - `docs/project/specs/context-management-ui.md`
  - `docs/project/specs/interactive-session-workflow.md`
  - `docs/project/PROJECT.md`
  - `docs/project/milestones/02-stability-and-polish.md`
  - `docs/architecture/core/ports/outbound/config_service.md`
  - `docs/architecture/core/services/session_pruning_service.md`

## Implementation Notes

### Deliverable 1: Contract – Rename Config Key
- Renamed `auto_pruning.global_context_threshold` to `auto_pruning.turn_context_threshold` in bundled `config.yaml`. Updated comment to reflect Turn-scope-only behavior.
- Fixed `test_yaml_config_adapter.py::test_auto_pruning_defaults_are_present` to assert the new key name (was asserting old key name, causing a Local Flaw during integration).
- Production code (`_apply_global_budget`) still reads `global_context_threshold` – backward compatibility will be handled in the Seam deliverable.
- No other changes needed; the `config_service.get_setting()` API is key-based and unaffected by semantics of the key name.

## Implementation Plan
### Summary of Changes
1. **`session_pruning_service.py`**: Refactor `_apply_global_budget` to:
   - Remove `system_prompt_tokens` parameter.
   - Read `turn_context_threshold` with backward compatibility fallback.
   - Sum only `scope == "Turn"` items for threshold comparison.
   - Remove the local `system_prompt_tokens` extraction in `prune()` at line 54.
2. **`config.yaml`**: Rename `global_context_threshold` to `turn_context_threshold`, update comment.
3. **`yaml_config_adapter.py`**: No changes needed — the `get_setting` API is key-based; backward compatibility is handled in the pruning service (read `turn_context_threshold`, fallback to `global_context_threshold`).
4. **All test files**: Rename `global_context_threshold` → `turn_context_threshold` in mock configs; remove `system_prompt_tokens` from `_apply_global_budget` calls.
5. **All doc files**: Update key name.

### Mermaid Diagram (Threshold Calculation Flow)
```mermaid
graph TD
    A[prune()] --> B[Read threshold from config]
    B --> C{Key exists?}
    C -->|turn_context_threshold| D[Use new key]
    C -->|global_context_threshold only| E[Use old key + log deprecation]
    C -->|Neither| F[Threshold = 0 → skip]
    D --> G[Sum Turn-scope items only]
    E --> G
    G --> H{Sum > threshold?}
    H -->|Yes| I[Prune largest Turn-scope files]
    H -->|No| J[No pruning]
```

### Test Harness Triad Strategy
- **Setup**: Use `create_context_item()` helper to build ProjectContext with mixed scopes (Turn, Session, System).
- **Driver**: Call `pruning_service.prune(context)` directly.
- **Observer**: Assert `item.selected` for pruning decisions; assert total token sum is not influenced by Session/System items.
- **Key Assertions**:
  - Threshold 15k, Turn=10k, Session=40k → no pruning (10k <= 15k, even though total is 52k).
  - Threshold 5k, Turn=10k → pruning triggers on largest Turn file.
  - `system_prompt_tokens=99999` → no effect on pruning decision.
  - Old config key still works.
