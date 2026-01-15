# Vertical Slice: Refactor Core Service Layer & Domain Model

*   **Source Brief:** [Brief 01: Comprehensive Refactoring](../../briefs/01-comprehensive-refactoring.md)

## 1. Business Goal

To improve the maintainability, testability, and long-term velocity of the `teddy` executor by refactoring its core service layer. We will decompose the monolithic `PlanService` into smaller, single-responsibility services, introduce a formal Dependency Injection (DI) container for cleaner composition, and strengthen the domain model's type safety. This addresses critical technical debt and establishes a more robust foundation for future development.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: Successful execution of a plan
*   **Given** a valid `plan.yaml` file with a `create_file` action.
*   **When** the user runs the `teddy` executor with that plan.
*   **Then** the new, refactored service layer (Orchestrator, Parser, Dispatcher) should successfully execute the plan.
*   **And** the target file should be created on the file system.
*   **And** the final execution report should indicate a `SUCCESS` status.

#### Example
*   `plan.yaml`:
    ```yaml
    actions:
      - type: create_file
        path: "hello.txt"
        content: "Hello, World!"
    ```
*   `ExecutionReport` (summary portion):
    ```yaml
    run_summary:
      status: SUCCESS
      ...
    ```

### Scenario 2: Failed execution of a plan
*   **Given** a `plan.yaml` file with an action that is designed to fail (e.g., editing a non-existent file).
*   **When** the user runs the `teddy` executor with that plan.
*   **Then** the new, refactored service layer should correctly handle the action's failure.
*   **And** the final execution report should indicate a `FAILURE` status with appropriate error details.

#### Example
*   `plan.yaml`:
    ```yaml
    actions:
      - type: edit
        path: "non_existent_file.txt"
        find: "foo"
        replace: "bar"
    ```
*   `ExecutionReport` (summary portion):
    ```yaml
    run_summary:
      status: FAILURE
      ...
    action_logs:
      - status: FAILURE
        details: "File not found: non_existent_file.txt"
        ...
    ```

### Scenario 3: Strengthened Domain Model
*   **Given** any plan execution that generates an execution report.
*   **When** the `ExecutionReport` domain model is instantiated.
*   **Then** its internal structure (e.g., for `run_summary` and `action_logs`) must be composed of strongly-typed dataclasses instead of generic dictionaries.

### Scenario 4: Clean Composition Root
*   **Given** the application is starting up.
*   **When** the composition root in `main.py` is initialized.
*   **Then** it must use a formal Dependency Injection (DI) container to assemble and provide all necessary application services.

## 3. Architectural Changes

-   **New Services (Hexagonal Core):**
    -   `PlanParser`: Responsible for reading and validating the plan file.
    -   `ActionDispatcher`: Responsible for mapping an action type to its concrete implementation and executing it.
    -   `ExecutionOrchestrator`: The main application service that coordinates the parser, dispatcher, and user interactor to run a plan from start to finish.
-   **Modified Domain Model (Hexagonal Core):**
    -   `ExecutionReport` and related models will be refactored to use strongly-typed dataclasses for all internal structures, eliminating dictionary-based "Data Model Drift".
-   **Modified Composition Root (Integration Layer):**
    -   `main.py`: Will be refactored to use a new DI container (e.g., `punq`) to manage dependency creation and injection.
-   **Modified Inbound Adapter:**
    -   `CLI Adapter`: The Typer commands will be updated to call the new `ExecutionOrchestrator` service instead of the old `PlanService`.
-   **Deprecated Service:**
    -   `PlanService`: Its responsibilities will be fully delegated to the new services, and it will be removed.

## 4. Interaction Sequence

1.  The `CLI Adapter` receives the command to execute a plan.
2.  The `CLI Adapter` requests the `ExecutionOrchestrator` service from the DI container.
3.  The `CLI Adapter` invokes the `ExecutionOrchestrator` to run the plan.
4.  The `ExecutionOrchestrator` uses the `PlanParser` to load and validate the plan from the specified file.
5.  For each action in the plan, the `ExecutionOrchestrator` uses the `ActionDispatcher` to execute the action.
6.  The `ExecutionOrchestrator` gathers the results from each action.
7.  The `ExecutionOrchestrator` constructs the final `ExecutionReport` domain model.
8.  The `CLI Adapter` receives the `ExecutionReport` and uses a formatter to present it to the user on the console.

## 5. Scope of Work

This checklist outlines the implementation steps for the developer. Each step should be completed in order.

### Phase 1: Implement Core Domain & Services

-   [ ] **Task 1: Refactor the Domain Model**
    -   [ ] READ the design document: [ExecutionReport Domain Model](../../contexts/executor/domain/execution_report.md)
    -   [ ] IMPLEMENT the strongly-typed `RunSummary`, `ActionLog`, and `ExecutionReport` dataclasses in the `teddy_executor.core.domain.models` package.

-   [ ] **Task 2: Implement the PlanParser Service**
    -   [ ] READ the design document: [PlanParser Service](../../contexts/executor/services/plan_parser.md)
    -   [ ] IMPLEMENT the `PlanParser` service in `teddy_executor.core.services.plan_parser`.
    -   [ ] IMPLEMENT unit tests for the `PlanParser` service.

-   [ ] **Task 3: Implement the ActionDispatcher Service**
    -   [ ] READ the design document: [ActionDispatcher Service](../../contexts/executor/services/action_dispatcher.md)
    -   [ ] IMPLEMENT the `ActionDispatcher` service in `teddy_executor.core.services.action_dispatcher`.
    -   [ ] IMPLEMENT unit tests for the `ActionDispatcher` service.

-   [ ] **Task 4: Implement the ExecutionOrchestrator Service**
    -   [ ] READ the design document: [ExecutionOrchestrator Service](../../contexts/executor/services/execution_orchestrator.md)
    -   [ ] IMPLEMENT the `ExecutionOrchestrator` service in `teddy_executor.core.services.execution_orchestrator`.
    -   [ ] IMPLEMENT unit tests for the `ExecutionOrchestrator` service.

### Phase 2: Wire and Deprecate

-   [ ] **Task 5: Implement the Dependency Injection Container**
    -   [ ] READ the DI strategy: [CLI Adapter DI & Composition Root](../../adapters/executor/inbound/cli.md#1-dependency-injection--composition-root)
    -   [ ] ADD the `punq` library as a project dependency using Poetry.
    -   [ ] REFACTOR `packages/executor/src/teddy_executor/main.py` to create and configure the `punq` container.
    -   [ ] UPDATE the `execute` command in `main.py` to resolve the `ExecutionOrchestrator` from the container and use it to run the plan.

-   [ ] **Task 6: Deprecate and Remove Old Code**
    -   [ ] DELETE the now-obsolete `PlanService` (`teddy_executor.core.services.plan_service`).
    -   [ ] REMOVE any unit tests associated with the old `PlanService`.
    -   [ ] UPDATE `docs/ARCHITECTURE.md` to remove the link to the deprecated `plan_service.md` and delete the file itself.
