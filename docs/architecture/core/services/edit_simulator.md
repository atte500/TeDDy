# Component Design: EditSimulator
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/services/edit_simulator.py`](/src/teddy_executor/core/services/edit_simulator.py)

## Purpose
Implements the `IEditSimulator` inbound port. It applies a sequence of FIND/REPLACE edits to an in-memory string using resilient fuzzy matching, without any file system access.

## Consumers
- [`TextualPlanReviewer`](../../adapters/inbound/textual_plan_reviewer.md): Renders unified diff previews of pending edits.
- [`PlanValidator`](./plan_validator.md): Proves each FIND/REPLACE pair matches during pre-flight validation.
- [Composition Root](/src/teddy_executor/container.py): Constructs the simulator.

## Dependencies
- **`find_best_match`** (`teddy_executor.core.services.validation_rules.edit_matcher`): Locates the best matching block and returns its score, ambiguity flag, and indentation offset.
- **`SearchTextNotFoundError`** (`teddy_executor.core.domain.models`): Raised when no block meets the threshold.
- **`MultipleMatchesFoundError`** (`teddy_executor.core.domain.models`): Raised on an ambiguous tie.
- **`DEFAULT_SIMILARITY_THRESHOLD`** (`teddy_executor.core.domain.models.plan`): The default fuzzy-match threshold.

## Class Invariants
- `stateless_pure`: The service holds no state and performs no I/O; every result depends only on its arguments.
- `line_ending_preservation`: An appended newline reuses the detected terminator (`\n` or `\r\n`) of the matched block.
- `ambiguity_guard`: A tie between equally scored candidates raises `MultipleMatchesFoundError` unless `match_all` is set.

## Inbound Ports
- **`IEditSimulator`**: Exposes the single `simulate_edits(...)` operation.

## Outbound Ports
None — the simulator declares no injected dependencies.

## Data Contracts
- **`EditPair`** (`TypedDict`, `total=False`): `find: str`, `replace: str`, `match_all: bool`.
- **Return tuple:** `tuple[str, list[float]]` — the transformed string and the per-edit similarity scores.

## Operations

### `simulate_edits(content, edits, threshold=DEFAULT_SIMILARITY_THRESHOLD, match_all=False) -> tuple[str, list[float]]`
- **Preconditions:** `content` is a string; each `edits` entry carries a `find` block.
- **Postconditions:** Returns the transformed string and the list of similarity scores, applying every pair in sequence. A per-edit `match_all` overrides the global flag.
- **Exceptions:** `SearchTextNotFoundError` when no match meets the threshold; `MultipleMatchesFoundError` on an ambiguous tie.
