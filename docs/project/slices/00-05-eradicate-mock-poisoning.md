# Slice: Eradicate Mock Poisoning

- **Status:** Planned
- **Milestone:** [Milestone 00 (Foundation/Tech Debt)](/docs/project/milestones/00-foundation.md)
- **Specs:** N/A
- **Prototype:** N/A
- **MRE:** N/A
- **Showcase:** N/A
- **Component Docs:**
  - [Test Harness: Setup Composition](/docs/architecture/tests/setup/composition.md)

## Business Goal

Systematically prevent "Mock Poisoning" (Signature Drift, Type Erasure, and State Leakage) across the TeDDy codebase. By enforcing auto-speccing, strict DI-based test doubles, and type preservation in the test harness, we ensure that test executions provide high-confidence verification of production behavior.

## Scenarios

> As an engineer or AI agent, I want the test harness and linters to strictly enforce mock integrity so that I am instantly alerted if a mocked component diverges from its real interface.

```gherkin
Given the TeDDy test suite
When a mock is registered for an Outbound Port
And the mock is called with arguments that do not match the real port's signature
Then the test must immediately fail with a signature mismatch error

Given the project linter configuration
When an agent or engineer attempts to import `unittest.mock.patch`
Then the CI pipeline must fail with a strict violation error
```

## Deliverables

- [x] **Harness** - `pyproject.toml`: Add Ruff rules (`flake8-tidy-imports.banned-api`) banning `unittest.mock.patch` and `mock.patch` to prevent State Leakage globally.
- [ ] **Refactor** - Cleanup `patch` and bare `MagicMock` in `tests/suites/acceptance/`.
- [ ] **Refactor** - Cleanup `patch` and bare `MagicMock` in `tests/suites/integration/`.
- [ ] **Refactor** - Cleanup `patch` and bare `MagicMock` in `tests/suites/unit/adapters/`.
- [ ] **Refactor** - Cleanup `patch` and bare `MagicMock` in `tests/suites/unit/core/`.
- [ ] **Refactor** - Cleanup remaining `patch` in `tests/conftest.py` and `tests/harness/`.
- [ ] **Harness** - `tests/harness/setup/mocking.py`: Refactor `register_mock` to apply `create_autospec(interface)` by default instead of a bare `MagicMock`. This systemically eliminates Signature Drift.
- [ ] **Refactor** - `tests/harness/setup/mocking.py`: Resolve the `Mocked = Any` Type Erasure alias. Provide proper type hints (using generics `TypeVar('T')` or intersection types) so that `register_mock` returns a type that satisfies Mypy while retaining mock tracking capabilities.
- [ ] **Refactor** - Test Suite: Run the test suite and fix any tests that break. *Note: Enforcing `create_autospec` will likely expose existing Signature Drift across the 406 mocks. Fix the test inputs/outputs to align with the real contracts.*
- [ ] **Harness** - `pyproject.toml`: Update `[tool.mypy]` to enable `warn_return_any = true` to surface any remaining type erasure risks.

## Implementation Notes

### Deliverable: Banned API Configuration
- Configured `TID251` in `pyproject.toml`.
- Initial audit revealed **114** violations across the codebase (primarily bare `MagicMock` imports and `patch` context managers).
- Decisions:
    - Banned `MagicMock` to force use of `register_mock` which provides centralized control over auto-speccing.
    - Banned `patch` to enforce Hexagonal DI and prevent state leakage.

## Delta Analysis

- `pyproject.toml` will have stricter linting configurations.
- `tests/harness/setup/mocking.py` will have a robust, type-safe, auto-specced mock factory.
- Various test files will be updated to remove `patch` and fix signature drift. No production logic in `src/` should be modified.

## Guidelines for Implementation

1. **Incremental Execution:** Perform the Ruff/`patch` removal first, run tests, and commit.
2. **The Autospec Fallout:** When `create_autospec` is added to `register_mock`, expect numerous tests to fail if their setups pass the wrong arguments to `mock.return_value`. Address these systematically per file.
3. **Type Safety:** Python's `unittest.mock` combined with Mypy is notoriously tricky. If `Mocked = Any` cannot be perfectly resolved without breaking the type system, prioritize a structural type cast like `cast(T, MagicMock(spec=T))` inside `register_mock`.
