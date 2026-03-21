# Performance Optimizations: Test Suite & CLI
- **Status:** Planned
- **Milestone:** N/A (Fast-Track)
- **Specs:** [performance_regression_v3.md](/docs/project/debugging/performance_regression_v3.md)

## 1. Business Goal
Drop the overall test suite execution time below the 10-second threshold and eliminate the ~1-2s startup latency in the `teddy` CLI by optimizing Pytest collection, lazy-loading heavy libraries, and deferring global dependency injection.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: Pytest Collection Restricted
The test suite should no longer waste time traversing non-test directories (like `.venv` or `.git`) during the collection phase.
#### Deliverables
- [ ] Update `pyproject.toml` to include `testpaths = ["tests"]` within the `[tool.pytest.ini_options]` block.

### Scenario 2: Mistletoe Lazy Loading
The heavy regex compilation penalty of the `mistletoe` library should be deferred until absolutely necessary, removing the import penalty from CLI startup and test collection.
#### Deliverables
- [ ] Refactor `src/teddy_executor/core/services/markdown_plan_parser.py` to lazy-load `mistletoe` dependencies.
- [ ] Refactor `src/teddy_executor/core/services/action_parser_complex.py` to lazy-load `mistletoe` dependencies.
- [ ] Refactor `src/teddy_executor/core/services/action_parser_strategies.py` to lazy-load `mistletoe` dependencies.
- [ ] Refactor `src/teddy_executor/core/services/parser_infrastructure.py` to lazy-load `mistletoe` dependencies.
- [ ] Ensure the tests in `test_lazy_loading_integration.py` remain green.

### Scenario 3: CLI Lazy Initialization
The Dependency Injection container should only be initialized when a CLI command is actively executed, rather than at module import time.
#### Deliverables
- [ ] In `src/teddy_executor/__main__.py`, replace the global `container = create_container()` with a cached `get_container()` getter function.
- [ ] Update all Typer command callbacks in `__main__.py` to call `get_container()` when resolving dependencies.
- [ ] **CRITICAL:** Update `tests/harness/setup/composition.py` and `tests/harness/setup/test_environment.py` to correctly patch the new `get_container()` logic. If you skip this, the test suite will fail because the global `container` attribute will no longer exist.

### Scenario 4: Worker I/O Bottleneck Mitigated
The file generation loop in the tree generator performance test should be reduced to prevent monopolizing a test worker with excessive synchronous I/O.
#### Deliverables
- [ ] Update `tests/suites/integration/adapters/outbound/test_tree_generator_performance.py` to reduce the loop from 5000 to 500 files.
- [ ] Adjust the `max_duration_ms` assertion to be tighter (e.g., `< 50ms`) to reflect the smaller payload.

### Scenario 5: Purge Legacy Action Models & Extract Exceptions
The `_legacy_models.py` file contains obsolete, strongly-typed action classes that were replaced by the dynamic `ActionData` model. We must purge this technical debt while preserving the custom exceptions still actively used by the domain.
#### Deliverables
- [ ] Create `src/teddy_executor/core/domain/models/exceptions.py`.
- [ ] Move `FileAlreadyExistsError`, `MultipleMatchesFoundError`, `SearchTextNotFoundError`, and `WebSearchError` into `exceptions.py`.
- [ ] Delete `src/teddy_executor/core/domain/models/_legacy_models.py`.
- [ ] Update `src/teddy_executor/core/domain/models/__init__.py` to export the exceptions from the new file.
- [ ] Fix all broken imports across the `src/` and `tests/` directories caused by this move.
- [ ] Delete the obsolete unit tests targeting the legacy models in `tests/suites/unit/core/domain/test_models.py`.

### Scenario 6: Zero-Cost Contract Enforcement (DbC)
Domain models currently use `raise ValueError` for invariant checks (e.g., in `Plan.__post_init__`). These consume compute cycles in production. They must be replaced with native `assert` statements so they can be compiled out in optimized builds.
#### Deliverables
- [ ] Refactor `src/teddy_executor/core/domain/models/plan.py` to replace `raise ValueError` with `assert` statements (e.g., `assert self.actions, "Plan must contain at least one action."`).
- [ ] Ensure all tests that previously asserted `pytest.raises(ValueError)` for domain model instantiation are updated to check for `AssertionError`.

## 3. Architectural Changes
This is a Fast-Track refactoring slice. No new architectural components or explicit Test Harness Triad scaffolding are required. The focus is strictly on optimizing existing configurations, lazy-loading imports, deferring initialization, and purging legacy technical debt.

*(Note: The migration from `MagicMock` to In-Memory Fakes and strict Unit DI boundaries is explicitly deferred to Milestone 09 `09-test-harness-v2.md` due to its extensive blast radius across the test suite).*
