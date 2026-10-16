# Component Design: IEditSimulator
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/ports/inbound/edit_simulator.py`](/src/teddy_executor/core/ports/inbound/edit_simulator.py)

## Purpose
Defines the inbound port for applying a sequence of FIND/REPLACE edits to an in-memory string. It powers pre-execution validation and unified diff previews without modifying any file. The port is implemented by the `EditSimulator` service.

## Consumers
- [`PlanValidator`](../../services/plan_validator.md): Uses the port to prove each FIND/REPLACE pair matches during pre-flight validation.
- [`TextualPlanReviewer`](../../../adapters/inbound/textual_plan_reviewer.md): Uses the port to render unified diff previews of pending edits.

## Dependencies
- **`DEFAULT_SIMILARITY_THRESHOLD`** (`teddy_executor.core.domain.models.plan`): Supplies the default fuzzy-match threshold.

## Class Invariants
- `read_only`: Implementations must never mutate a file on disk; all work happens on in-memory strings.

## Inbound Ports
- **`IEditSimulator`**: Exposes the single `simulate_edits(...)` operation to consumers.

## Outbound Ports
None — the port requires no injected dependencies.

## Data Contracts
- **`EditPair`** (`TypedDict`, `total=False`): `find: str`, `replace: str`, `match_all: bool`.
- **Return tuple:** `tuple[str, list[float]]` — the transformed string and the per-edit similarity scores.

## Operations

### `simulate_edits(content, edits, threshold=DEFAULT_SIMILARITY_THRESHOLD, match_all=False) -> tuple[str, list[float]]`
- **Preconditions:** `content` is a string and each `edits` entry carries a `find` block.
- **Postconditions:** Returns the transformed string and the list of similarity scores, applying every pair in sequence.
- **Exceptions:** `ValueError` when a `find` block is not found or matches ambiguously.
