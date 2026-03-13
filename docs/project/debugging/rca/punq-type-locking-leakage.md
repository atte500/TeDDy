# RCA: Container State Leakage and Mock Pollution in Sequential Runs

- **Status:** Resolved ✅
- **Resolution Date:** 2026-03-13
- **MRE:** [docs/project/debugging/mre/stale-container-leakage.md](/docs/project/debugging/mre/stale-container-leakage.md)

## 1. Summary
The `teddy` CLI suite suffered from widespread test failures (30+) when run sequentially or in a single process. Tests would frequently fail with `AssertionError` ("Expected call but got 0 times") or `TypeError` (passing Mocks into PyYAML). This was caused by the global `punq.Container` instance in `src/teddy_executor/__main__.py` caching and "locking" its registrations, preventing test fixtures from effectively mocking dependencies in subsequent test turns.

## 2. Investigation Summary
A series of verification spikes identified three key failure mechanisms:
1.  **Type Locking:** In `punq`, once a type is resolved (e.g., `container.resolve(IService)`), its registration becomes immutable. Any further calls to `container.register(IService, ...)` are silently ignored.
2.  **Singleton Staleness:** Core orchestration services (Replanner, Planner, PlanningService) were registered as singletons. They cached their dependencies (like the FileSystemManager) on the first resolution and never refreshed them.
3.  **Bootstrap Collision:** The `bootstrap` command in `__main__.py` attempts to re-register the file system adapter to anchor it to the project root. This re-registration was ineffective if the file system had already been resolved (common in interactive or sequential modes).

## 3. Root Cause
The root cause is a misunderstanding of the `punq` library's immutability model. The system was designed assuming that registrations could be overwritten at any time (Last-Registration-Wins). In reality, `punq` only supports Last-Registration-Wins *before* a type has been resolved. Once resolved, the container instance becomes effectively read-only for that type.

## 4. Verified Solution
The solution requires two simultaneous changes to ensure a clean slate for every turn:

### Part A: Universal Transient Scope
All logic-heavy orchestration and planning services must be changed from the default singleton scope to `punq.Scope.transient`. This ensures they are re-constructed with the latest container registrations on every request.

```python
# src/teddy_executor/container.py updates
container.register(ActionDispatcher, scope=punq.Scope.transient)
container.register(ActionExecutor, scope=punq.Scope.transient)
container.register(ExecutionOrchestrator, scope=punq.Scope.transient)
container.register(PlanningService, scope=punq.Scope.transient)
container.register(SessionReplanner, scope=punq.Scope.transient)
container.register(SessionPlanner, scope=punq.Scope.transient)
container.register(SessionService, scope=punq.Scope.transient)
```

### Part B: Container Freshness in Tests
The `container` fixture in `tests/conftest.py` must replace the entire global container instance, not just re-register mocks on the existing one.

```python
# tests/conftest.py updates
@pytest.fixture
def container(monkeypatch):
    c = create_container() # Create a BRAND NEW instance
    monkeypatch.setattr(teddy_executor.__main__, "container", c)
    return c
```

## 5. Preventative Measures
1.  **Avoid Global Singletons for Logic:** Services that depend on the file system or environment should never be singletons in a CLI tool where the environment (root directory) can change via bootstrapping.
2.  **Strict Freshness in Fixtures:** All DI-related fixtures must operate on a fresh container instance to prevent leakage across tests.

## 6. Implementation Notes
The fix was applied in two parts:
1. **Container Scoping:** All logic-heavy services and infrastructure adapters in `src/teddy_executor/container.py` were moved to `punq.Scope.transient`. This ensures that they are reconstructed for every resolution request, allowing the `bootstrap` callback to successfully re-anchor the file system in sequential runs.
2. **Test Isolation:** The `container` fixture in `tests/conftest.py` now resets the global `teddy_executor.__main__.container` to a fresh instance. Additionally, tests found to be polluting the filesystem (e.g., `test_enhanced_validation.py`) were updated to use `tmp_path` and `monkeypatch.chdir`.

## 7. Recommended Regression Test
Run the entire test suite sequentially to ensure it passes without side effects:
`poetry run pytest -n 0`
