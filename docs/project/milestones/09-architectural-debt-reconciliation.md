# Milestone 09: Architectural Debt Reconciliation

- **Status:** Completed

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
- [x] [Slice 09-02: Structural Hardening & Security](../slices/09-02-structural-hardening-and-security.md)
- [x] [Slice 09-03: File Length Debt Reconciliation](../slices/09-03-file-length-debt-reconciliation.md)
- [x] [Slice 09-04: Final Debt Cleanup](../slices/09-04-final-debt-cleanup.md)
- [x] [Slice 09-05: Type-Safe Dead Code Whitelisting](../slices/09-05-type-safe-vulture-whitelist.md)

## 5. Technical Debt
- [x] [Code Quality] Transition to type-safe Vulture whitelist (Slice 09-05).
- [x] [Code Quality] Refactor `src/teddy_executor/core/services/session_orchestrator.py` to meet 300-line limit (currently 487 lines -> 286 lines).
- [x] [Code Quality] Refactor `src/teddy_executor/adapters/outbound/shell_adapter.py` to meet 300-line limit (currently 340 lines).
- [x] [Code Quality] Refactor `src/teddy_executor/core/services/markdown_plan_parser.py` to meet 300-line limit (currently 244 lines).
- [x] [Code Quality] Refactor `src/teddy_executor/adapters/inbound/cli_helpers.py` to meet 300-line limit (currently 237 lines).
- [x] [Code Quality] Refactor `src/teddy_executor/adapters/inbound/textual_plan_reviewer_previews.py` to meet 300-line limit (currently 239 lines).
- [x] [Code Quality] Refactor `src/teddy_executor/core/services/execution_orchestrator.py` to meet 300-line limit (currently 332 lines).
- [x] [Code Quality] Refactor `src/teddy_executor/core/services/planning_service.py` to meet 300-line limit (currently 335 lines).
- [x] [Code Quality] Resolve Mypy duplicate module error for `slice_00_05_logic` vs `prototypes/slice_00_05_logic`.
- [x] [Code Quality] Prune unused variables and imports identified by Vulture in ports and adapters.
- [x] [Code Quality] Resolve Ruff magic value (PLR2004) warnings in core service unit tests.
- [x] [Code Quality] Refactor `tests/harness/setup/test_environment.py` to meet 300-line limit (currently 308 lines).
- [x] [Architectural] Refactor `ActionFactory` to group port dependencies and reduce argument count (PLR0913).
- [x] [Architectural] Refactor `ActionFactory` to remove `punq` dependency.
- [x] [Architectural] Refactor `TestEnvironment` to hide `punq` registration logic.
- [x] [Security] Resolve pip-audit vulnerabilities: lxml (6.1.0), pytest (9.0.3), python-dotenv (1.2.2).
- [x] [Code Quality] Resolve existing Ruff complexity/statements errors in `ShellAdapter`, `ExecutionOrchestrator`, and `PlanningService`.
- [x] [Code Quality] Resolve Mypy duplicate module error in `test_unified_mock.py`.
- [x] [Code Quality] Resolve Ruff magic value (PLR2004) warnings in `tests/suites/unit/core/services/test_execution_orchestrator.py`.
- [x] [Code Quality] Prune unused variables and imports identified by Vulture in ports and adapters.
- [x] [Code Quality] Resolve Mypy duplicate module error for `slice_00_05_logic` in `test_session_orchestrator_resume.py`.
