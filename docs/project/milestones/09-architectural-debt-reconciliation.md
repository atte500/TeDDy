# Milestone 09: Architectural Debt Reconciliation

- **Status:** In Progress

## 1. Goal (The "Why")
To harden the system's architecture by resolving systemic technical debt that compromises testability, isolation, and maintenance. This milestone focuses on enforcing strict boundaries and improving the developer experience within the test harness.

## 2. Proposed Solution (The "What")
1. **DI Boundary Enforcement:** Physically prevent core logic from depending on the DI framework.
2. **ActionFactory Refactor:** Transition from Service Locator to Constructor Injection.
3. **TestHarness Simplification:** Provide a high-level, port-centric mocking API in `TestEnvironment`.

## 3. Guidelines (The "How")
- **Test Harness Triad Strategy:** Use `UnifiedMock` within `TestEnvironment.mock_port` to ensure sync/async parity.
- **Branch by Abstraction:** Ensure the existing test suite remains green throughout the refactoring by updating the composition root (`container.py`) in lockstep with `ActionFactory`.

## 4. Vertical Slices
- [x] [Slice 09-01: DI Boundary Enforcement](../slices/09-01-di-boundary-enforcement.md)
- [ ] [Slice 09-02: Structural Hardening & Security](../slices/09-02-structural-hardening-and-security.md)

## 5. Technical Debt
- [ ] [Code Quality] Refactor `src/teddy_executor/core/services/session_orchestrator.py` to meet 300-line limit (currently 487 lines).
- [ ] [Code Quality] Refactor `src/teddy_executor/adapters/outbound/shell_adapter.py` to meet 300-line limit (currently 335 lines).
- [x] [Code Quality] Refactor `tests/harness/setup/test_environment.py` to meet 300-line limit (currently 308 lines).
- [ ] [Architectural] Refactor `ActionFactory` to group port dependencies and reduce argument count (PLR0913).
- [x] [Architectural] Refactor `ActionFactory` to remove `punq` dependency.
- [x] [Architectural] Refactor `TestEnvironment` to hide `punq` registration logic.
- [ ] [Security] Resolve pip-audit vulnerabilities: lxml (6.1.0), pytest (9.0.3), python-dotenv (1.2.2).
- [ ] [Code Quality] Resolve existing Ruff complexity/statements errors in `ShellAdapter`, `ExecutionOrchestrator`, and `PlanningService`.
- [ ] [Code Quality] Resolve Mypy duplicate module error in `test_unified_mock.py`.
