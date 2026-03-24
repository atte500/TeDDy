# Systemic TUI Timeout Regression
- **Status:** Unresolved
- **Target Agent:** Debugger

## 1. Failure Context
After implementing UI mode toggling and updating the DI container to support `ConsolePlanReviewer` vs `TextualPlanReviewer`, 38 tests started failing with timeouts. The failures occur because the system is attempting to launch the Textual TUI (`TextualPlanReviewer`) during automated tests, which then times out after 5 seconds as it waits for user interaction that cannot happen in the test environment.

The regression affects Acceptance, Integration, and Unit tests. It seems the DI container is resolving the real implementation instead of the mocks provided by `TestEnvironment` or `composition.py`.

## 2. Steps to Reproduce
Run the full test suite from the project root:
```shell
poetry run pytest
```

## 3. Expected vs. Actual Behavior
**Expected:** Tests should use the mocked `IPlanReviewer` (registered in `composition.py` as an `autouse` fixture) or no reviewer at all (as configured in `TestEnvironment.setup()`), allowing them to proceed non-interactively.
**Actual:** `ExecutionOrchestrator` resolves a real `TextualPlanReviewer`, which initiates `app.run()`, causing `pytest-timeout` failures.

## 4. Relevant Code
- `src/teddy_executor/container.py`: The `_get_reviewer` factory logic which reads from config.
- `src/teddy_executor/core/services/execution_orchestrator.py`: The `_perform_interactive_review` and `_process_plan_actions` methods.
- `tests/harness/setup/composition.py`: The `mock_plan_reviewer` fixture.
- `tests/harness/setup/test_environment.py`: The `_register_default_mocks` method and container patching logic.

## 5. Root Cause Analysis
The regression was caused by a conflict between the DI container's registration logic and the Typer CLI lifecycle.
1. **Production Registry:** `container.py` registered `IPlanReviewer` as a transient factory. This factory resolved `IConfigService` to determine whether to return a `TextualPlanReviewer` (TUI) or `ConsolePlanReviewer`.
2. **CLI Bootstrap:** Typer's `@app.callback()` (`bootstrap`) re-registers `IConfigService` as a real `YamlConfigAdapter` every time a command is invoked.
3. **Test Shadowing Failure:** While `TestEnvironment` patched the global container, it did not provide an explicit registration for `IPlanReviewer`. Because `punq` resolution follows a "last-one-wins" policy, and the factory registration in `container.py` was technically "available", the resolution of `IPlanReviewer` during tests triggered the production factory.
4. **TUI Launch:** Since `bootstrap` re-registered a real `IConfigService` (which defaults to `ui_mode: "tui"`), the factory returned a `TextualPlanReviewer`. Any test running in `interactive` mode (the default for the `execute` command) then triggered the TUI app, which hung indefinitely in the headless test environment.

## 6. Implementation Notes
1. **Test Harness Fix:** Updated `TestEnvironment._register_default_mocks()` to explicitly register `IPlanReviewer` as `None`. This ensures that even if `IConfigService` is re-registered as real, the `IPlanReviewer` dependency is satisfied by the `None` instance rather than triggering the production factory.
2. **Acceptance Test Fix:** Updated `test_context_aware_editing_modifies_create_action` to pass `interactive=True`. A recent change to `ExecutionOrchestrator` correctly added a guard that bypasses the reviewer if `interactive` is `False`. Since the `CliTestAdapter` defaults to `False`, the test was being bypassed and failing its assertions.
3. **Verification:** Confirmed that `test_context_aware_editing_modifies_create_action` passes and the 38 timeouts are resolved across the suite.

## 7. Architectural Remediation
- **Explicit Test Contracts:** All core inbound ports that trigger UI or side-effects MUST be explicitly registered as `None` or `Mock` in `TestEnvironment` to prevent accidental resolution of production factories.
- **Interactive Defaults:** Clarified `CliTestAdapter` and `ExecutionOrchestrator` documentation regarding the requirement of the `interactive` flag for reviewer-dependent tests.
