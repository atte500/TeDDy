# Brief 01: Comprehensive Refactoring

This document outlines a plan to refactor the `teddy` executor to improve maintainability, address technical debt, and establish robust patterns for future development.

## Problem Definition (The Why)

The primary driver for this work is the high cost of change within the codebase. This manifests in two key ways:
1.  **Brittle Tests:** The test suite, particularly at the acceptance level, is tightly coupled to implementation details and raw string output, requiring significant and costly refactoring whenever new features are added.
2.  **Known Technical Debt:** The architecture document explicitly lists several architectural and design issues, such as a complex composition root and data model inconsistencies, which hinder development velocity.

The goal of this initiative is to address these root causes to make the codebase more maintainable, reliable, and easier to extend.

## Selected Solution (The What)

We will execute a multi-faceted refactoring strategy that addresses the core design, domain model, and testing layers of the application.

1.  **Core Application Refactoring:** Decompose the monolithic `PlanService` into smaller, single-responsibility classes and introduce a dependency injection (DI) container to manage the application's composition root cleanly.
2.  **Domain Model Refinement:** Strengthen the `ExecutionReport` domain model by replacing weakly-typed dictionaries with strongly-typed dataclasses, eliminating the "Data Model Drift."
3.  **Test Strategy Unification:** Standardize all acceptance tests on a "white-box" pattern using `typer.testing.CliRunner` to eliminate brittleness. Refactor unit tests in lockstep with the core application changes to be simpler and more focused.
4.  **Documentation Cleanup:** Condense the `ARCHITECTURE.md` file to be a purely high-level document.

## Implementation Analysis (The How)

Our deep-dive analysis of the codebase confirmed the following key findings:

-   **`main.py`:** The composition root manually instantiates and wires all application dependencies, making it complex and brittle.
-   **`plan_service.py`:** This core service violates the Single Responsibility Principle by handling parsing, user interaction, action dispatch, and reporting. Its high number of dependencies makes it difficult to test and maintain.
-   **`models.py`:** The `ExecutionReport` dataclass uses generic dictionaries, an inconsistency with the otherwise strongly-typed domain model.
-   **Acceptance & Unit Tests:** The test suites suffer from the design issues in the core application. Acceptance tests rely on a slow and fragile `subprocess` pattern, while the unit tests for `PlanService` are complex, suffer from high setup costs, and are not properly isolated.

## Vertical Slices

This initiative is broken down into the following high-level, actionable slices:

- [x] **Slice 1: Refactor the Core Service Layer & Domain Model.** This slice focuses on improving the core application's design and type safety.
    -   Decompose the monolithic `PlanService` into smaller, single-responsibility services (`PlanParser`, `ActionDispatcher`, `ExecutionOrchestrator`).
    -   Introduce a formal Dependency Injection (DI) container in `main.py`.
    -   Refactor the `ExecutionReport` model to use strongly-typed dataclasses, eliminating the "Data Model Drift".
    -   Relocate presentation logic and consolidate error handling out of the core services.

- [ ] **Slice 2: Modernize the Test Suite.** This slice focuses on establishing robust, maintainable testing patterns.
    -   Create a new, standardized "white-box" acceptance test helper using `typer.testing.CliRunner`.
    -   Migrate a pilot test (`test_walking_skeleton.py`) to the new helper to serve as a template.
    -   Refactor the unit test suite to align with the newly decomposed services, creating smaller, focused tests with consistent fixture patterns.
    -   Deprecate and remove legacy test helpers.

- [ ] **Slice 3: Finalize Documentation and CLI Polish.** This slice focuses on cleaning up documentation and improving the CLI's internal structure.
    -   Condense the "Architectural Notes" section in `ARCHITECTURE.md` to be a concise, high-level summary.
    -   Refactor the input handling logic (file vs. clipboard) in the `execute` command into a dedicated helper function.
