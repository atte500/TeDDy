# Slice: DI Boundary Enforcement
- **Status:** Planned
- **Milestone:** [09-architectural-debt-reconciliation](../milestones/09-architectural-debt-reconciliation.md)
- **Specs:** [di-boundary-rules](../specs/di-boundary-rules.md)
- **Component Docs:** [ARCHITECTURE](../../architecture/ARCHITECTURE.md)

## Business Goal
Enforce Hexagonal Architecture principles by decoupling the core domain from the Dependency Injection framework, ensuring the system is transparent, testable, and robust against framework changes.

## Scenarios

### Scenario 1: Physical Boundary Enforcement
> As an Architect, I want to prevent `punq` from being imported in the core directory so that architectural isolation is physically enforced.
```gherkin
Given a file "src/teddy_executor/core/services/violation.py" containing "import punq"
When I run the pre-commit hooks
Then the commit MUST fail
And the error message MUST explain the DI Boundary Rule
```

### Scenario 2: ActionFactory Constructor Injection
> As a Developer, I want `ActionFactory` to receive its dependencies via constructor so that its requirements are transparent and easily mockable in unit tests.
```gherkin
Given I am refactoring "ActionFactory"
When I remove the "container" argument from the constructor
And I add explicit arguments for "IShellExecutor", "IFileSystemManager", "IUserInteractor", "IWebSearcher", "IWebScraper", and "IConfigService"
Then the "ActionFactory" MUST still be able to create all action types
And "src/teddy_executor/core/services/action_factory.py" MUST NOT import "punq"
```

### Scenario 3: Declarative Mocking API
> As a Developer, I want to mock a port in a single call so that I don't have to manage DI container registration manually in every test.
```gherkin
Given a unit test using "TestEnvironment"
When I call "env.mock_port(IShellExecutor)"
Then a "UnifiedMock" for "IShellExecutor" MUST be registered in the container
And the method MUST return the mock instance for further configuration
```

## Deliverables
1. [x] **Harness** - Implement `check-core-di-boundary` local pre-commit hook in `.pre-commit-config.yaml`.
2. [ ] **Seam** - Add `mock_port` method to `TestEnvironment` in `tests/harness/setup/test_environment.py`.
3. [ ] **Logic** - Refactor `ActionFactory` in `src/teddy_executor/core/services/action_factory.py` to use constructor injection.
4. [ ] **Wiring** - Update `src/teddy_executor/container.py` to resolve and inject dependencies into `ActionFactory`.
5. [ ] **Refactor** - Update `tests/harness/setup/test_environment.py` and existing tests to use `env.mock_port()`.
6. [ ] **Cleanup** - Remove `punq` import from `src/teddy_executor/core/services/action_factory.py`.

## Delta Analysis
- The `ActionFactory` currently resolves handlers on-the-fly from the container. After refactoring, it will use stored references to the injected ports.
- The `TestEnvironment` currently has multiple `_register_*_mocks` methods. These will be consolidated/refactored to use the new `mock_port` utility to reduce duplication.
- The pre-commit hook will use a simple `grep -r` check scoped to `src/teddy_executor/core/`.

## Implementation Notes

### Deliverable 1: DI Boundary Hook
- **YAML Syntax Trap:** Discovered that complex shell commands in `.pre-commit-config.yaml` containing colons (`:`) followed by spaces (e.g., in `echo` statements) trigger `InvalidConfigError: mapping values are not allowed in this context`.
- **Solution:** Used a YAML literal block scalar (`|`) for the `entry` field to safely encapsulate the bash script.
- **Exclusion Rationale:** `src/teddy_executor/core/services/action_factory.py` is temporarily excluded from the hook. This is a "Ratchet" strategy: the hook prevents *new* violations immediately, while the exclusion allows us to commit the refactored code that eventually removes the `punq` dependency from `ActionFactory`. The exclusion will be removed in Deliverable #6.
- **Verification:** Verified via `tests/suites/acceptance/test_di_boundary_enforcement.py` which uses a temporary `violation_spike.py` to prove the hook correctly rejects `punq` imports.
