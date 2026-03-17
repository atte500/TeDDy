# Slice: Refine Similarity Logic

- **Status:** Planned
- **Milestone:** Fast-Track
- **Specs:** [docs/project/specs/plan-format-validation.md](/docs/project/specs/plan-format-validation.md)

## 1. Business Goal
Improve the consistency and maintainability of the similarity matching logic by centralizing configuration and standardizing score precision.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: Global Threshold Configuration
**Given** a configuration file `.teddy/config.yaml` with `similarity_threshold: 0.8`
**When** a plan with an `EDIT` action is executed
**Then** the validation should use `0.8` as the threshold for fuzzy matching.
**And** if no value is set in `config.yaml`, it should fallback to `0.95`.

#### Deliverables
- [ ] Update `EditActionValidator` to retrieve `similarity_threshold` from `IConfigService`.
- [ ] Update `container.py` to inject `IConfigService` into `EditActionValidator`.

### Scenario 2: Score Rounding and Comparison
**Given** a fuzzy match with a raw similarity score (e.g., 0.94999)
**When** calculating the score for comparison or reporting
**Then** the score should be rounded to two decimal places (e.g., 0.95).
**And** comparison against the threshold should use this rounded value.

#### Deliverables
- [ ] Refactor `src/teddy_executor/core/services/validation_rules/edit_matcher.py` to round scores to 2 decimal places.
- [ ] Remove module-level `FUZZY_RATIO_THRESHOLD` and pass the threshold as a parameter to all matching functions.

### Scenario 3: Plan-Level Threshold Deprecation
**Given** a Markdown plan containing `- **Similarity Threshold:** 0.8` in an `EDIT` action metadata
**When** the plan is parsed
**Then** the parser should ignore this value in favor of the global configuration.

#### Deliverables
- [ ] Remove/Deprecate "Similarity Threshold" parsing in `src/teddy_executor/core/services/action_parser_complex.py`.

## 3. Architectural Changes
- **Dependency Injection:** `EditActionValidator` now requires `IConfigService`.
- **Logic Centralization:** The hardcoded `0.95` default is moved from the validation rules/matcher to the implementation layer (or config fallback).
