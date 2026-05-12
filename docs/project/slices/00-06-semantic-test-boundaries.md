# Slice: Semantic Test Boundaries

- **Status:** Planned
- **Milestone:** [Milestone 00 (Foundation/Tech Debt)](/docs/project/milestones/00-foundation.md)
- **Specs:** N/A
- **Prototype:** N/A
- **MRE:** N/A
- **Showcase:** N/A
- **Component Docs:**
  - [Test Harness: Setup Composition](/docs/architecture/tests/setup/composition.md)

## Business Goal

Enforce strict Test Pyramid boundaries (Semantic Deduplication) across the TeDDy codebase. By preventing cross-layer imports and ensuring Acceptance tests exclusively use the Subcutaneous Test Harness, we eliminate semantic overlap, reduce test fragility, and enable CI to automatically reject architectural violations.

## Scenarios

*(Note: As a pure refactoring slice, external behavior remains unchanged. Existing tests must remain green.)*

## Deliverables

- [ ] **Refactor** - Move all miscategorized core service integration tests (the 35 violations currently in `tests/suites/integration/core/services/`) to their proper home in `tests/suites/unit/core/services/` (or rewrite them if they are genuinely testing adapters).
- [ ] **Refactor** - Refactor the 8 violating Acceptance tests (e.g., `test_context_aware_editing.py`, `test_tui_rationale_parsing.py`, `test_context_management_ui.py`, `test_prompt_auto_approval.py`, etc.) to use the Test Harness Triad (e.g., CLI drivers or the `container` fixture) instead of directly importing and instantiating `teddy_executor.core.services.*`.
- [ ] **Harness** - `.github/workflows/ci.yml`: Add `git grep` guardrails to the `quality-checks` job to permanently enforce Rule B (Ban core imports in integration) and Rule C (Ban internal service imports in acceptance).

## Implementation Notes

*(To be filled by the Developer during implementation)*

## Delta Analysis

- `tests/suites/integration/core/services/` will likely be emptied and deleted, with its contents migrating to `unit/`.
- Acceptance tests will be structurally modified to rely solely on `tests/harness/`.
- `.github/workflows/ci.yml` will have two new `run` steps under `quality-checks`.

## Guidelines for Implementation

1. **Incremental Execution:** Move the integration tests first, run the test suite, and commit. Then tackle the Acceptance tests.
2. **Acceptance Refactoring:** When replacing direct instantiations (like `MarkdownPlanParser()`) in Acceptance tests, look at how the `TestEnvironment` or `tui_driver.py` interacts with the system. You must drive the SUT from the outside-in.
3. **CI Guardrails:** The `git grep` commands to add to CI are:
   - `git grep -nE "(from|import) .*teddy_executor\.core" tests/suites/integration/ && { echo "Semantic Overlap"; exit 1; } || true`
   - `git grep -nE "(from|import) .*teddy_executor\.core\.services" tests/suites/acceptance/ && { echo "Semantic Overlap"; exit 1; } || true`
   *(Ensure these run successfully in the bash environment of the GitHub Action).*
