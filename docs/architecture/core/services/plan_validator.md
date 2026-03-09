**Status:** Implemented
**Introduced in:** [Slice 01: Markdown Report Generator](../../slices/01-markdown-report-generator.md)

## 1. Purpose / Responsibility
To implement the `IPlanValidator` inbound port. This service orchestrates the pre-flight validation of a plan by delegating to specialized, action-specific validator strategies. It ensures validation errors provide rich context, including code blocks for failed `FIND` patterns, to enable AI self-correction.

## 2. Ports
-   **Implements (Inbound):** `IPlanValidator`
-   **Uses (Outbound):** `IFileSystemManager` (via its validator strategies).

## 3. Implementation Details
This service is implemented using a **Standardized Strategy Pattern** with constructor-based dependency injection.

1.  **Validator Strategies:** A set of validator classes (e.g., `CreateActionValidator`, `EditActionValidator`) implement a common `IActionValidator` protocol. These classes are encapsulated in the `teddy_executor.core.services.validation_rules` module and receive their required dependencies (like `IFileSystemManager`) via their constructors.
2.  **Strategy Dispatcher:** The `PlanValidator` service maintains a list of these injected validators. Its `validate` method iterates through the validators to find one that can handle the current action type.
3.  **Orchestration & Accumulation:** The `validate` method iterates through the actions in the plan. For each action, it delegates to the appropriate validator strategy and accumulates a complete list of `ValidationError` objects.
4.  **Rich Feedback:** When `FIND` blocks do not match, the validator uses a sliding window and `difflib` to locate the closest match and append a diff to the error report, drastically improving the AI's ability to self-correct.
5.  **`EXECUTE` Action Safety:** Validation ensures that each `EXECUTE` action contains a non-empty command block. The protocol allows shell chaining and inline directives (like `cd` or `export`), shifting responsibility for command cleanliness to the agent's prompting.

This approach adheres to the Open/Closed Principle, allowing new validation rules to be added by creating new strategy classes without modifying the orchestrator.

## 4. Data Contracts / Methods
This service implements the `validate` method as defined by the `IPlanValidator` port.
