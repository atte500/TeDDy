# Spec: Dependency Injection Boundary Rules
- **Status:** Active

## Overview / Problem Statement
The current implementation of `ActionFactory` and the `TestEnvironment` relies on the **Service Locator anti-pattern**, where core domain services receive the DI `Container` directly and resolve dependencies dynamically.

This leads to several systemic failures:
1. **Architectural Leakage:** The `core/` logic is coupled to the `punq` library, violating Hexagonal Architecture principles.
2. **Opaque Testing:** AI agents and developers struggle to untangle the test harness because mocked ports are hidden inside container overrides rather than being passed explicitly.
3. **Fragility:** Changes to the DI wiring can cause distant, hard-to-debug failures in core logic.

## Guiding Principles / Core Logic
To make the TeDDy workflow anti-fragile, we enforce the following rules:

1. **Mandatory Constructor Injection:** All dependencies MUST be passed explicitly via constructors. Defaulting to `None` or dynamic resolution via a global or passed container is strictly forbidden.
2. **Framework Isolation:** The `src/teddy_executor/core/` directory MUST NOT import or depend on `punq` or any other DI framework.
3. **Declarative Testing:** The `TestEnvironment` must hide the DI container from the user. Mocking a port should be a single, high-level call (e.g., `env.mock_port(IShellExecutor)`).

## Technical Specification

### 1. The Pre-commit Boundary Gate (Physical Enforcement)
The Architect MUST implement a custom pre-commit hook as part of the foundational pre-commit suite to physically enforce the boundary.
- **Scope:** Strictly enforced on all files within `src/teddy_executor/core/`.
- **Validation Rule:** Use a regex-based scanner (or `import-linter`) to detect any occurrence of `import punq` or `from punq`.
- **Action:** Halt the commit process and report the violation with a clear explanation of the DI Boundary Rule.

### 2. ActionFactory Refactoring
The `ActionFactory` must be refactored to remove the `punq.Container` dependency.
- **Before:** `def __init__(self, container: punq.Container): ...`
- **After:** `def __init__(self, shell: IShellExecutor, fs: IFileSystemManager, interactor: IUserInteractor, ...): ...`
- **Wiring:** The `container.py` (Composition Root) is the only place allowed to resolve these dependencies and pass them to the factory.

### 3. TestEnvironment Simplification
The `TestEnvironment` must be updated to support a Port-centric mocking API.
- **Goal:** Enable `env.mock_port(IShellExecutor)` which internally handles the `punq` registration and `UnifiedMock` synchronization.

## Guidelines
1. **Foundation First:** The Architect must first implement the CI enforcement script to prevent further regressions.
2. **Branch by Abstraction:** When refactoring the `ActionFactory`, ensure the existing test suite continues to pass by utilizing the `UnifiedMock` synchronization during the transition.
3. **Harness Alignment:** Update the `TestEnvironment` only after the `ActionFactory` refactor is proven in isolation.
