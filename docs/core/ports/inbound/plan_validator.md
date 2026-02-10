**Status:** Planned
**Introduced in:** [Slice 01: Markdown Report Generator](../../slices/01-markdown-report-generator.md)

## 1. Purpose / Responsibility
Defines the contract for any service that performs pre-flight validation of a `Plan` domain object. This port ensures that a plan's proposed actions are checked for common issues (e.g., `FIND` block mismatches, creating existing files) before execution begins.

## 2. Ports
This component is an **Inbound Port**. It defines a use case that is driven by primary adapters like the CLI.

## 3. Implementation Details
This port is expected to be implemented by a `PlanValidator` service. The implementation should process all actions within the `Plan` and aggregate any validation failures.

## 4. Data Contracts / Methods

### `validate(self, plan: Plan) -> list[ValidationError]`
-   **Description:** The primary method to execute the validation process.
-   **Preconditions:**
    -   `plan` must be a valid `Plan` domain object.
-   **Postconditions:**
    -   Returns a list of `ValidationError` objects.
    -   An empty list signifies that the plan has passed all validation checks.
-   **Invariants:** This method must not cause any side effects or modify the state of the filesystem.

### `ValidationError` (Data Transfer Object)
A simple, immutable data structure representing a single validation failure.
-   **`action_index: int`**: The zero-based index of the action in the plan that failed.
-   **`message: str`**: A human-readable message explaining the validation error.
