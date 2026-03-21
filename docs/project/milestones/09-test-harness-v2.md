# Milestone 09: Test Harness V2 (Fakes & Strict DI)

## 1. Goal (The "Why")
The current test harness relies heavily on `MagicMock` and global Dependency Injection (DI) container bootstrapping for unit tests. This causes significant performance degradation and results in fragile, reflection-heavy tests. We need to transition to In-Memory Fakes and enforce strict Unit DI boundaries to guarantee high-performance test execution and enforce pure Contract-First Design.

## 2. Proposed Solution (The "What")
- Introduce stateful In-Memory Fakes for all Outbound Ports (e.g., `FakeFileSystemManager`, `FakeLlmClient`, `FakeShellExecutor`).
- Enforce a strict architectural boundary where unit tests instantiate target components directly, explicitly forbidding the use of the global `container` fixture.
- Establish the Test Harness (`tests/harness/`) as a first-class architectural citizen with its own dedicated unit tests to guarantee the performance of Fakes and Observers.

## 3. Implementation Guidelines (The "How")
- **Fakes over Mocks:** Design lightweight, native Python Fakes (e.g., dictionary-backed repositories) that implement the exact outbound port interfaces without using `unittest.mock`.
- **Harness Refactoring:** Update the `TestEnvironment` to register these Fakes instead of Mocks when setting up isolated test scopes.
- **State-Based Verification:** Migrate tests from using behavioral verification (`mock.assert_called_with()`) to state-based verification using the `Observer` components of the Test Harness Triad.

## 4. Vertical Slices
- [ ] **Slice 1: Harness Self-Testing & Core Fakes**
  Implement unit tests for the Test Harness itself. Create the core In-Memory Fakes (`FakeFileSystemManager`, `FakeShellExecutor`) and verify their execution speed.
- [ ] **Slice 2: Migration of Adapters & Setup**
  Refactor `tests/harness/setup/composition.py` and `TestEnvironment` to replace default `MagicMock` registrations with the new Fakes.
- [ ] **Slice 3: Strict Unit DI Boundary Enforcement**
  Systematically migrate all unit tests in `tests/suites/unit/` to manually instantiate components instead of resolving them from the global `container`.
