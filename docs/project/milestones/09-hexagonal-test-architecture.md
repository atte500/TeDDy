# Milestone 09: Hexagonal Test Architecture
- **Status:** Planned
- **Specs:** N/A

## 1. Goal (The "Why")
To elevate the TeDDy testing suite to a "first-class architectural citizen" by treating it conceptually as a Primary Driving Adapter (Hexagonal Architecture). We must eliminate test setup rot, prevent monolithic test scripts, and formally document our Test Harness Triad (Setup, Driver, Observer). The ultimate goal is to apply the exact same strict code quality guardrails (SLOC and complexity limits) to our test files as we do to our production files, mathematically forcing the extraction of reusable test infrastructure.

## 2. Proposed Solution (The "What")
1.  **Formalize the Test Harness:** Map existing and new test utilities as formally documented components under the `testing` boundary, utilizing a standard `tests/conftest.py` entry point with lazy-loading fixtures to ensure accurate coverage tracking.
2.  **Sequential Refactoring:** Iteratively refactor the Acceptance, Integration, and Unit test suites to utilize these formal Test Contexts and Builders, significantly DRYing up setup logic.
3.  **Unified Architectural Guardrails:** Once the suites are clean, update `.pre-commit-config.yaml` and `ARCHITECTURE.md` to remove all leniency for tests. The 300 SLOC limit and Cyclomatic Complexity rules will apply universally to force compliance moving forward.

## 3. Implementation Guidelines (The "How")
*   **Test Architecture Strategy:** The Architect must officially define a new layer in `ARCHITECTURE.md` mapping the `tests/` directory as Primary Adapters.
*   **Documentation:** Test components (like Builders or Contexts) must be documented in `docs/architecture/tests/` to establish clear Pre/Post-conditions and data contracts for test setup.
*   **Refactoring Order:** Start with Acceptance/Integration tests (which tend to have the heaviest setup), then move to Unit tests.
*   **Flipping the Switch:** The final slice must actively modify the linter configurations to drop the previous exemptions for test files.

## 4. Technical Specifications
*   **Unified SLOC Limit:** 300 lines max per file (including `src/` and `tests/`, excluding `spikes/`).
*   **Unified Complexity Limits:** Cyclomatic Complexity limit of 9; Statement limit of 40 per function.

## 5. Vertical Slices
1.  **09-01: Test Harness Blueprinting:** Formally document existing test utilities as architectural components and identify missing Object Mothers.
2.  **09-02: Refactor Acceptance & Integration Suites:** Extract duplicated setup logic in high-level tests into the formal DSLs/Builders.
3.  **09-03: Refactor Unit Suite:** Apply Test Contexts to massive unit test files (e.g., `test_session_service.py`) to reduce setup boilerplate.
4.  **09-04: Architectural Guardrails & Unified Linting:** Update `pyproject.toml`, `.pre-commit-config.yaml`, and `ARCHITECTURE.md` to enforce the strict, unified limits.
