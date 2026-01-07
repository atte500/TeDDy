# Vertical Slice 08: Refactor Action Dispatching

### 1. Business Goal

This is a **technical refactoring slice**. Its goal is to improve the long-term health, maintainability, and scalability of the codebase. By replacing the `if/elif` action dispatching logic in the `PlanService` with a more robust dispatch map pattern (e.g., a dictionary), we reduce the friction of adding new action types in the future, increasing development velocity and reducing the risk of bugs.

### 2. Acceptance Criteria (Scenarios)

Since this is a refactoring, the primary goal is to improve internal quality without changing any external behavior.

*   **Scenario 1: All existing acceptance tests MUST pass**
    *   **Given:** The full suite of acceptance tests for `execute`, `create_file`, `read`, and `edit` actions.
    *   **When:** The tests are run against the codebase after the refactoring.
    *   **Then:** All tests must pass without any modification to the test cases themselves. The output of the `teddy` command must be identical to the output before the refactoring.

*   **Scenario 2: Code structure is improved**
    *   **Given:** The `PlanService._execute_single_action` method contains an `if/elif isinstance(...)` block for dispatching.
    *   **When:** The refactoring is complete.
    *   **Then:** The `if/elif` block must be removed from `_execute_single_action`.
    *   **And:** It must be replaced by a dictionary lookup (dispatch map) that maps action types (classes) to their corresponding handler methods.

### 3. Interaction Sequence (Post-Refactor)

1.  The `PlanService` receives a concrete `Action` object (e.g., `ExecuteAction`, `CreateFileAction`).
2.  The `PlanService._execute_single_action` method looks up the action's class (e.g., `ExecuteAction`) in an internal dispatch map (e.g., `self.action_handlers`).
3.  The dispatch map returns the corresponding handler method (e.g., `self._handle_execute`).
4.  The handler method is invoked with the action object.
5.  The handler returns an `ActionResult`.

### 4. Scope of Work (Components)

-   [ ] **Hexagonal Core:** Refactor `services/plan_service.md` to document the new dispatch map strategy.
-   [ ] **Hexagonal Core:** Modify `src/teddy/core/services/plan_service.py`:
    -   Implement a dispatch map (dictionary) in the `__init__` method.
    -   Replace the `if/elif` chain in `_execute_single_action` with a lookup in the dispatch map.
-   [ ] **Testing:** All existing unit, integration, and acceptance tests must pass. No new tests are required unless to specifically cover the dispatch map lookup itself.
