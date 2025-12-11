# Vertical Slice 03: Refactor Action Dispatching

### 1. Business Goal
This is a technical refactoring slice. Its goal is to improve the long-term health, maintainability, and scalability of the codebase. By replacing the `if/elif` action dispatching logic in the `PlanService` with a more robust pattern (like the Strategy or Command pattern), we reduce the friction of adding new action types in the future, increasing development velocity.

### 2. Acceptance Criteria (Scenarios)

*   **Scenario 1: Existing functionality is preserved for `execute` action**
    *   **Given:** A plan contains a valid `execute` action.
    *   **When:** The executor runs the plan after the refactoring.
    *   **Then:** The command is executed successfully and the execution report is identical to the one produced before the refactoring.

*   **Scenario 2: Existing functionality is preserved for `create_file` action**
    *   **Given:** A plan contains a valid `create_file` action.
    *   **When:** The executor runs the plan after the refactoring.
    *   **Then:** The file is created successfully and the execution report is identical to the one produced before the refactoring.

*   **Scenario 3: Code structure is improved**
    *   **Given:** The `PlanService._execute_single_action` method contains an `if/elif` block for dispatching.
    *   **When:** The refactoring is complete.
    *   **Then:** The `if/elif` block is removed and replaced by a dictionary lookup or a similar scalable pattern.
    *   **And:** The validation logic in the `Action` model's `__post_init__` is moved to action-specific classes.

### 3. Interaction Sequence (Post-Refactor)
1.  The `CLI Adapter` invokes the `RunPlanUseCase`.
2.  The `PlanService` receives the raw action data.
3.  A new `ActionFactory` component is responsible for validating the raw data and creating a specific `Action` subclass (e.g., `ExecuteAction`, `CreateFileAction`).
4.  The `PlanService` uses a dispatch map (dictionary) to look up the appropriate handler/strategy for the given action type.
5.  The selected handler is executed, which in turn may use outbound ports like `ShellExecutor` or `FileSystemManager`.
6.  The handler returns an `ActionReport`.

### 4. Scope of Work (Components)

*   **Domain Model (`docs/core/domain_model.md`):**
    *   [ ] Refactor the monolithic `Action` model into a base class with specific subclasses (e.g., `ExecuteAction`, `CreateFileAction`).
    *   [ ] Move validation logic from `__post_init__` into the respective subclasses.
*   **Core - Services:**
    *   [ ] Create a new `ActionFactory` or similar mechanism responsible for creating action objects from raw data.
    *   [ ] Modify `PlanService` to remove the `if/elif` block and use a dispatch map to execute actions.
*   **Tests:**
    *   [ ] All existing acceptance and integration tests MUST pass without modification to their logic.
    *   [ ] New unit tests should be created for the `ActionFactory` and the new action subclasses.
