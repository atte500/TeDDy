# Slice 09-04: Architectural Guardrails & Unified Linting
- **Status:** Planned
- **Milestone:** [Milestone 09: Hexagonal Test Architecture](../milestones/09-hexagonal-test-architecture.md)
- **Specs:** N/A

## 1. Business Goal
To finalize the elevation of tests to first-class architectural citizens by enforcing the exact same quality standards on test code as production code. This "flips the switch" on automated enforcement, ensuring the system remains modular and the Test Harness Triad is utilized to keep files focused and maintainable.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: Refactor SLOC Offenders
**Goal:** Bring the identified test files into compliance with the unified 300-line limit.
- **Precondition:** `test_file_system_adapter.py` (344 lines) and `test_reviewer_app.py` (302 lines) exceed the limit.
- **Success Condition:** `test_reviewer_app.py` is split into `test_reviewer_app.py` and `test_reviewer_logic.py`.
- **Success Condition:** `test_file_system_adapter.py` is refactored to use a new harness observer for file-matching assertions.
- **Success Condition:** Both files are < 300 SLOC.
#### Deliverables
- [ ] Refactor `tests/suites/unit/adapters/inbound/test_reviewer_app.py`.
- [ ] Refactor `tests/suites/integration/adapters/outbound/test_file_system_adapter.py`.

### Scenario 2: Unified Guardrail Enforcement
**Goal:** Mathematically enforce quality standards across the entire codebase.
- **Precondition:** `.pre-commit-config.yaml` has separate, lenient rules for tests.
- **Success Condition:** `file-length-tests` hook is removed.
- **Success Condition:** `file-length-src` is renamed to `file-length-python` and applied to `^(src|tests)/` with a strict 300-line limit.
- **Success Condition:** All Ruff complexity and statement checks are active for both `src/` and `tests/`.
#### Deliverables
- [ ] Update `.pre-commit-config.yaml` to unify SLOC limits and consolidate hooks.
- [ ] Update `pyproject.toml` to ensure Ruff checks explicitly target all directories.

### Scenario 3: CI/CD Parity & Streamlining
**Goal:** Eliminate redundancy in the CI pipeline while maintaining 100% parity with local checks.
- **Precondition:** `ci.yml` duplicates several checks already present in `pre-commit`.
- **Success Condition:** `ci.yml` is updated to remove redundant `vulture` and `test-pyramid` steps, relying on the `pre-commit` run.
- **Success Condition:** CI remains "Green" on all platforms.
#### Deliverables
- [ ] Streamline `.github/workflows/ci.yml`.

### Scenario 4: Codify "System Law" [✓]
**Goal:** Document the new unified standards in the project's single source of truth.
- **Precondition:** `ARCHITECTURE.md` contains lenient language or outdated standards.
- **Success Condition:** `ARCHITECTURE.md` defines the unified 300 SLOC, 9 Complexity, and 40 Statement limits as absolute project rules.
#### Deliverables
- [✓] Update `docs/architecture/ARCHITECTURE.md`.

## 3. Architectural Changes

### Unified Guardrail Implementation
The core architectural shift is the removal of the "test exemption" for quality gates. This is implemented via:

1.  **Consolidated Hook Logic:** The `pre-commit` configuration will now treat the repository as a single quality domain.
2.  **Interaction Sequence:**
    *   **Developer Commit:** Triggers `pre-commit` -> Runs Ruff (Complexity/Statements) -> Runs Unified SLOC check -> Runs Test Pyramid Check -> Runs Full Test Suite.
    *   **CI Pipeline:** Triggers on Push -> Runs `pre-commit run --all-files` (Single Source of Truth) -> Runs external/slow checks (jscpd, pip-audit).

### Updated Component Designs
- **Test Harness Observer:** A new observer component `tests/harness/observers/file_system_observer.py` will be introduced to encapsulate complex file-system assertions (e.g., verifying directory contents and file matching), enabling the refactoring of large integration tests.