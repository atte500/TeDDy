# Slice: Structural Hardening & Security
- **Status:** Planned
- **Milestone:** [09-architectural-debt-reconciliation](../milestones/09-architectural-debt-reconciliation.md)
- **Specs:** [di-boundary-rules](../specs/di-boundary-rules.md)
- **Component Docs:**
    - [ActionPorts](../../architecture/core/domain/action_ports.md)
    - [ActionFactory](../../architecture/core/services/action_factory.md)
    - [IEditSimulator](../../architecture/core/ports/inbound/edit_simulator.md)

## Business Goal
Harden the system's structural integrity and security posture by resolving high-complexity debt, enforcing type safety in the test harness, and patching known vulnerabilities.

## Scenarios

### Scenario 1: Security Compliance
> As a Security Engineer, I want the project's dependencies to be free of known vulnerabilities so that the tool is safe for production environments.
```gherkin
Given a pyproject.toml with updated versions for lxml, pytest, and python-dotenv
When I run "poetry run pip-audit"
Then the command MUST return an exit code of 0
And no vulnerabilities MUST be reported
```

### Scenario 2: ActionFactory Dependency Hardening
> As a Developer, I want ActionFactory to receive its ports via a grouped DTO so that its constructor remains simple and stable.
```gherkin
Given an "ActionPorts" DTO containing all required outbound ports
When I refactor "ActionFactory" to accept "ActionPorts" in its constructor
Then "ActionFactory" MUST maintain its behavior for all action types
And Ruff MUST NOT report a PLR0913 (Too many arguments) violation
```

### Scenario 3: Structural Complexity Reduction
> As a Maintainer, I want core execution logic to be decomposed into small, focused methods so that the system is easier to audit and extend.
```gherkin
Given a set of services (ShellAdapter, ExecutionOrchestrator, PlanningService) with high complexity scores
When I refactor these services to extract logic into private helper methods
Then Ruff MUST report 0 violations for C901, PLR0912, and PLR0915 in these files
And the full test suite MUST remain green
```

### Scenario 4: Test Harness Type Safety
> As a Developer, I want the TestEnvironment to be fully type-checked so that I get immediate feedback on incorrect mock configurations.
```gherkin
Given a TestEnvironment utilizing "UnifiedMock"
When I run "mypy src tests"
Then no errors MUST be reported in "tests/harness/setup/test_environment.py"
And no "duplicate module" errors MUST be reported for "test_unified_mock.py"
```

## Deliverables
- [x] **Contract** - Implement `ActionPorts` DTO in `src/teddy_executor/core/domain/models/action_ports.py`.
- [ ] **Seam** - Fix `IEditSimulator.simulate_edits` signature in `src/teddy_executor/core/ports/inbound/edit_simulator.py` to match implementation.
- [ ] **Logic** - Refactor `ActionFactory` constructor to use `ActionPorts`.
- [ ] **Wiring** - Update `src/teddy_executor/container.py` to construct `ActionPorts` and inject it into `ActionFactory`.
- [ ] **Logic** - Decompose `ShellAdapter._run_subprocess` to resolve C901/PLR0915/PLR0912.
- [ ] **Logic** - Decompose `ExecutionOrchestrator.execute` to resolve C901/PLR0915/PLR0912.
- [ ] **Logic** - Decompose `PlanningService` generation methods to resolve C901/PLR0915.
- [ ] **Harness** - Refactor `UnifiedMock` in `tests/harness/setup/mocking.py` to satisfy Mypy type-checking for abstract ports.
- [ ] **Refactor** - Resolve duplicate module conflict for `test_unified_mock.py`.
- [ ] **Cleanup** - Prune any leftover debt markers (# noqa) from refactored files.

## Delta Analysis
- **UnifiedMock Risks:** The current `UnifiedMock` uses dynamic attribute access which Mypy rejects. This must be refactored to use a more structured proxy or explicit type annotations in `TestEnvironment.mock_port`.
- **ShellAdapter Sensitivity:** `_run_subprocess` contains critical isolation logic (SIGTTIN/SIGTTOU guards). Decomposing this requires extreme care to ensure the child process isolation is not compromised.
- **Mypy Cache:** The "duplicate module" error is likely a result of Mypy's cache seeing the same module name in different directories if not properly configured. Investigation is required in `pyproject.toml`.

## Guidelines for Implementation
- Use **Extract Method** as the primary refactoring pattern.
- Ensure each extracted method has a single responsibility (e.g., `_prepare_posix_kwargs`, `_handle_windows_scripting`).
- Verify each atomic deliverable with `ruff` and `mypy` before moving to the next.

## Implementation Notes

### Deliverable: ActionPorts DTO
- Implemented `ActionPorts` as a frozen dataclass in `src/teddy_executor/core/domain/models/action_ports.py`.
- Encountered and resolved a circular import: `models/__init__.py` -> `ActionPorts` -> `ports/outbound/__init__.py` -> `IMarkdownReportFormatter` -> `execution_report` -> `models/__init__.py`.
- **Resolution:** Used `TYPE_CHECKING` guards and string forward references in `ActionPorts` to break the runtime dependency on the `ports.outbound` package during initialization.
- Verified with full test suite and `mypy`.
