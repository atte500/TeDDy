# MRE: Stale Container Leakage in Sequential Test Runs

## 1. Summary
The `teddy` CLI uses a global `punq.Container` instance in `src/teddy_executor/__main__.py`. In sequential test runs using `pytest` (especially with `typer.testing.CliRunner`), this container instance persists across multiple `invoke()` calls.

Tests that do not explicitly use the `container` fixture (which patches the global variable) fall back to the real global container. Subsequent tests then inherit the "dirty" state (registrations, resolved singletons) from previous runs.

Attempts to fix this by re-initializing the container in the `bootstrap` callback (the Typer global callback) failed because `bootstrap` runs at command-execution time and overwrites any mocks injected by the test fixtures before the command logic executes.

## 2. Reproduction Steps
Run the enhanced validation tests sequentially:
`poetry run pytest tests/acceptance/test_enhanced_validation.py -n 0`

## 3. Expected Behavior
Each `runner.invoke` call should operate in a completely isolated environment where the container and all its services are fresh.

## 4. Actual Behavior
Tests pass in isolation or with high parallelism (separate processes) but fail in sequential runs because the `PlanValidator` and its rules hold onto stale `IFileSystemManager` instances from previous test runs.

## 5. Constraints
- The solution must NOT overwrite mocks injected by pytest fixtures.
- The solution must ensure that `bootstrap` re-anchoring of the file system actually updates the dependencies of already-resolved services.
