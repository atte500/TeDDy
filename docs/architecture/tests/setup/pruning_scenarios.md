# Component Design: PruningScenarios (Setup)
- **Status:** Implemented
- **Source:** [`tests/harness/setup/pruning_scenarios.py`](/tests/harness/setup/pruning_scenarios.py)

## Purpose
Supplies the canonical retention-boundary scenarios a pruning-service test needs to drive every batch boundary without creating real session directories. Data only: it imports no pruning-service code, so a test cannot couple to the implementation it exercises.

## Consumers
- [`test_pruning_scenarios_harness.py`](/tests/suites/unit/test_pruning_scenarios_harness.py): pins the scenario contract and reads turn ids through the production extractor.
- [`test_session_pruning_retention_window.py`](/tests/suites/unit/core/services/test_session_pruning_retention_window.py): drives the batched retention window over sequential and sparse turn ids.
- [`test_session_pruning_retention_wiring.py`](/tests/suites/acceptance/test_session_pruning_retention_wiring.py): composes the same builder with real adapters in the acceptance tracer bullet.

## Dependencies
None. Standard library plus the `ContextItem` domain model.

## Class Invariants
- `one_item_per_id`: `turn_context(ids)` builds exactly one selected `Turn`-scoped `ContextItem` per id, preserving declaration order.
- `zero_padded_paths`: `turn_path(id)` renders `<TURN_ROOT>/<NN>/plan.md`, so the production `_extract_turn_id` reads the id back unchanged.
- `gaps_are_gaps`: explicit sparse ids stay sparse, because retention counts turn ids rather than entries.
- `shared_token_count`: every built item carries `TURN_TOKEN_COUNT`.

## Inbound Ports
None. The module exposes data and builders:
- `TURN_ROOT`, `TURN_TOKEN_COUNT`: canonical constants.
- `turn_path(turn_id) -> str`.
- `turn_context(turn_ids) -> list[ContextItem]`.
- `sequential_turn_context(turn_count, start=1) -> list[ContextItem]`.

## Outbound Ports
None. The module reads no port.

## Data Contracts
- **`ContextItem`** (`teddy_executor.core.domain.models.project_context`): the selected, `Turn`-scoped item each builder emits.

## Operations

### `turn_path(turn_id) -> str`
- **Preconditions:** `turn_id` is a positive integer.
- **Postconditions:** returns the zero-padded turn path under `TURN_ROOT`.
- **Exceptions:** None.

### `turn_context(turn_ids) -> list[ContextItem]`
- **Preconditions:** None.
- **Postconditions:** returns one selected `Turn`-scoped item per id in the given order, each with `TURN_TOKEN_COUNT` tokens.
- **Exceptions:** None.

### `sequential_turn_context(turn_count, start=1) -> list[ContextItem]`
- **Preconditions:** None.
- **Postconditions:** returns `turn_count` consecutive turns from `start` upward.
- **Exceptions:** None.
