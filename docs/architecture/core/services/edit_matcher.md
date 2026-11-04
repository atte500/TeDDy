# Component Design: EditMatcher
- **Status:** Refactoring
- **Source:** [`src/teddy_executor/core/services/validation_rules/edit_matcher.py`](/src/teddy_executor/core/services/validation_rules/edit_matcher.py)

## Purpose
Locates the file window that best matches a FIND block, scores it with the raw similarity ratio, decides whether the match is ambiguous across candidate windows, and reports the indentation offset that lets the EDIT seam re-indent the REPLACE block.

## Consumers
- [`EditSimulator`](./edit_simulator.md): Applies FIND/REPLACE pairs and raises `MultipleMatchesFoundError` with the exact candidate count from the decision record.
- [`PlanValidator`](./plan_validator.md): Its injected `EditActionValidator` strategy uses the closest-match diff for not-found diagnostics and the decision record for the ambiguity message facts.

## Dependencies
- **`gather_candidate_starts`** (`teddy_executor.core.services.validation_rules.edit_matcher_heuristics`): Seeds candidate window starts from the tiered anchor, fuzzy, substring, and exhaustive heuristics.
- **`DEFAULT_SIMILARITY_THRESHOLD`** (`teddy_executor.core.domain.models.plan`): The inclusive default acceptance floor (`0.95`).
- **`difflib`** (standard library): `SequenceMatcher` ratios and `ndiff` character-level diagnostics.

## Class Invariants
None — the module is stateless. The following behavioral invariants hold on every call:
- `raw_ratio_comparison`: Every ambiguity comparison and every returned score uses the raw difflib ratio; scores are not rounded on return.
- `promotion_to_one`: `_apply_indentation_bonus` and `_apply_substring_boost` assign exactly `1.0`, so `score < 1.0` means no verbatim and no indentation-only match.
- `exact_candidate_count`: Every seeded candidate reaches refinement, and `candidate_count` counts refined candidates at or above the threshold; `content.count(find)` is never consulted.
- `legacy_tuple_stability`: `find_best_match` and `find_best_match_and_diff` keep their four-way tuple contract; the richer record is exposed additively through `find_best_match_ex`.

## Inbound Ports
None — module-level functions consumed directly by core services; no inbound port is declared.

## Outbound Ports
None — the module performs no I/O and holds no state.

## Data Contracts
- **`MatchResult`** (`NamedTuple`): `match: str`, `score: float`, `is_ambiguous: bool`, `offset: int`, `runner_up: float`, `candidate_count: int`. `score` and `runner_up` are raw ratios; `offset` is the constant indentation delta (`0` when none); `candidate_count` counts refined candidates at or above the threshold.
- **`AMBIGUITY_HINT`** (`str`): The shared hint appended by both ambiguity messages, unified on the list-item `Match All: true` phrasing.
- **Similarity constants**: `LARGE_BLOCK_LINE_LIMIT` (large-block sub-sampling boundary) and `SUB_SAMPLE_PASS_THRESHOLD` (coarse large-block acceptance floor). The candidate evaluation cap is retired; every seeded candidate is refined.

## Operations

### `find_best_match_ex(file_content, find_block, threshold=DEFAULT_SIMILARITY_THRESHOLD) -> MatchResult`
- **Preconditions:** Both inputs are strings; `threshold` is inclusive and lies in `[0.0, 1.0]`.
- **Postconditions:** Returns the six-field decision record. `score` is the raw ratio of the winning window; `runner_up` is the second-highest refined ratio (`0.0` when fewer than two candidates exist); `candidate_count` is exact. Ambiguity is true when the top ratio is at or above the threshold and either a second candidate ties it or the runner-up also reaches the threshold; a sub-threshold top is never reported as ambiguous.
- **Exceptions:** None.

### `find_best_match(file_content, find_block, threshold=DEFAULT_SIMILARITY_THRESHOLD) -> tuple[str, float, bool, int]`
- **Preconditions:** Same as `find_best_match_ex`.
- **Postconditions:** Legacy adapter over the decision record; returns `(match, score, is_ambiguous, offset)` with the raw score.
- **Exceptions:** None.

### `find_best_match_and_diff(file_content, find_block, threshold=DEFAULT_SIMILARITY_THRESHOLD) -> tuple[str, float, bool, int]`
- **Preconditions:** Same as `find_best_match_ex`.
- **Postconditions:** Derives the decision from the same record and returns `(diff_text, score, is_ambiguous, offset)`. `diff_text` is a character-level `ndiff` rendered only for a non-ambiguous fuzzy match; it is empty otherwise.
- **Exceptions:** None.
