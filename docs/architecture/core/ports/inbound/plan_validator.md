**Status:** Refactoring
**Introduced in:** [Slice 09-05](/docs/project/slices/09-05-plan-validation-self-correction.md)

## 1. Purpose / Responsibility
Defines the contract for performing pre-flight validation of a `Plan` domain object before execution. In session-aware mode, it validates action targets against the current working context.

## 2. Ports
This component is an **Inbound Port**. It defines a use case that is driven by primary adapters like the CLI.

## 3. Implementation Details
This port is expected to be implemented by a `PlanValidator` service. The implementation should process all actions within the `Plan` and aggregate any validation failures.

## 4. Data Contracts / Methods

### `validate(self, plan: Plan, context_paths: Dict[str, Sequence[str]] = None) -> list[ValidationError]`
-   **Description:** The primary method to execute the validation process.
-   **Preconditions:**
    -   `plan` must be a valid `Plan` domain object.
-   **Postconditions:**
    -   Returns a list of `ValidationError` objects.
    -   An empty list signifies that the plan has passed all validation checks.
-   **Context Handling:**
    -   If `context_paths` is provided, it should contain keys `Session` and `Turn`.
    -   **EDIT Rule:** File must be in `Session` OR `Turn` context.
    -   **PRUNE Rule:** File must be in `Turn` context ONLY.
    -   **READ Rule:** File must NOT be in `Session` OR `Turn` context.
-   **Invariants:** This method must not cause any side effects or modify the state of the filesystem.

### `ValidationError` (Data Transfer Object)
A simple, immutable data structure representing a single validation failure.
-   **`action_index: int`**: The zero-based index of the action in the plan that failed.
-   **`message: str`**: A human-readable message explaining the validation error.
