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
- [`EditMatcher`](./edit_matcher.md): Provides `find_best_match_ex`, returning the decision record (`match`, raw `score`, `is_ambiguous`, `offset`, `runner_up`, `candidate_count`) and the shared `AMBIGUITY_HINT`.
- **`SearchTextNotFoundError`** (`teddy_executor.core.domain.models`): Raised when no block meets the threshold.
- **`MultipleMatchesFoundError`** (`teddy_executor.core.domain.models`): Raised on an ambiguous match.
- **`DEFAULT_SIMILARITY_THRESHOLD`** (`teddy_executor.core.domain.models.plan`): The default fuzzy-match threshold.

## Class Invariants
- `stateless_pure`: The service holds no state and performs no I/O; every result depends only on its arguments.
- `line_ending_preservation`: An appended newline reuses the detected terminator (`\n` or `\r\n`) of the matched block, and a matched region that lacks a trailing newline (an intra-line fragment match) drops the authored REPLACE terminator so it is never injected mid-line.
- `ambiguity_guard`: A fuzzy winner with a second candidate at or above the threshold, or a tie at or above the threshold, raises `MultipleMatchesFoundError` unless `match_all` is set. The exception message carries the exact candidate count and the shared `AMBIGUITY_HINT`, never a hardcoded `2`.

## Inbound Ports
- **`IEditSimulator`**: Exposes the single `simulate_edits(...)` operation.

## Outbound Ports
None — the simulator declares no injected dependencies.

## Data Contracts
- **`EditPair`** (`TypedDict`, `total=False`): `find: str`, `replace: str`, `match_all: bool`.
- **`MatchResult`** (`EditMatcher`): `match: str`, `score: float`, `is_ambiguous: bool`, `offset: int`, `runner_up: float`, `candidate_count: int`; the simulator consumes every field.
- **Return tuple:** `tuple[str, list[float]]` — the transformed string and the per-edit similarity scores.
- **`SearchTextNotFoundError`** (`ValueError`): Raised when no candidate meets the similarity threshold.
- **`MultipleMatchesFoundError`** (`Exception`): Raised on an ambiguous tie or competing candidate at or above threshold, carrying the exact candidate count.

## Operations

### `simulate_edits(content, edits, threshold=DEFAULT_SIMILARITY_THRESHOLD, match_all=False) -> tuple[str, list[float]]`
- **Preconditions:** `content` is a string; each `edits` entry carries a `find` block.
- **Postconditions:** Returns the transformed string and the list of similarity scores, applying every pair in sequence. A per-edit `match_all` overrides the global flag.
- **Exceptions:**
  - `SearchTextNotFoundError`: No match meets the similarity threshold.
  - `MultipleMatchesFoundError`: Ambiguous match occurs due to a tie or a second candidate scoring at or above threshold.
