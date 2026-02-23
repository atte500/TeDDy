**Status:** Implemented
**Introduced in:** [Slice 01: Markdown Report Generator](../../slices/01-markdown-report-generator.md)

## 1. Purpose / Responsibility
To implement the `IPlanValidator` inbound port. This service orchestrates the pre-flight validation of a plan by delegating to specialized, action-specific validator strategies. It ensures validation errors provide rich context, including code blocks for failed `FIND` patterns, to enable AI self-correction.

## 2. Ports
-   **Implements (Inbound):** `IPlanValidator`
-   **Uses (Outbound):** `IFileSystemManager` (via its validator strategies).

## 3. Implementation Details
This service will be implemented using the **Strategy Pattern**, as decided in the architectural exploration phase.

1.  **Validator Strategies:** A set of validator classes will be created, each responsible for validating a single action type (e.g., `CreateActionValidator`, `EditActionValidator`). Each of these classes will implement a common `IActionValidator` interface.
2.  **Strategy Factory/Dispatcher:** The `PlanValidator` service will use a factory or a simple dictionary to map action types to their corresponding validator strategy instances.
3.  **Orchestration & Accumulation:** The `validate` method iterates through the actions in the plan. For each action, it retrieves the appropriate validator strategy, executes it, and accumulates a complete list of `ValidationError` objects rather than halting on the first error.
4.  **Rich Feedback:** When `FIND` blocks do not match, the validator uses a sliding window and `difflib` to locate the closest match and append a diff to the error report, drastically improving the AI's ability to self-correct.

This approach adheres to the Open/Closed Principle, allowing new validation rules to be added by creating new strategy classes without modifying the orchestrator.

## 4. Data Contracts / Methods
This service implements the `validate` method as defined by the `IPlanValidator` port.
