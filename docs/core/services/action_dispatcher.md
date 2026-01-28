# Application Service: ActionDispatcher

The `ActionDispatcher` is a single-responsibility service within the hexagonal core. Its purpose is to take a validated `ActionData` object, resolve the appropriate action implementation, execute it, and return a log of the result.

## 1. Design Principles

-   **Single Responsibility:** This service only dispatches and executes a single action. It does not parse plans or orchestrate the overall execution flow.
-   **Factory-driven:** It relies on the `ActionFactory` to decouple itself from concrete action implementations. This adheres to the Open/Closed Principle, as new action types can be added to the factory without modifying the dispatcher.
-   **Result-oriented:** Its output is always an `ActionLog` domain object, providing a consistent result contract for its callers.

## 2. Dependencies

-   **Application Services:**
    -   `ActionFactory`: To create instances of action handlers based on the action type.

## 3. Public Interface

The `ActionDispatcher` service exposes a single method.

### `dispatch_and_execute`
Resolves and executes a single action, returning its result.

**Status:** Implemented

```python
from teddy_executor.core.domain.models import ActionData, ActionLog
from teddy_executor.core.services.action_factory import IActionFactory

class ActionDispatcher:
    def __init__(self, action_factory: IActionFactory):
        self._action_factory = action_factory

    def dispatch_and_execute(self, action_data: ActionData) -> ActionLog:
        """
        Takes an ActionData object, finds the corresponding action handler
        via the factory, executes it, and returns the result as an ActionLog.

        This method is responsible for creating the ActionLog and populating
        it with the outcome of the execution, including the original
        `description` from the ActionData.

        It will catch any exceptions during action execution and wrap them
        in a FAILURE ActionLog.

        Args:
            action_data: The data for the action to be executed.

        Returns:
            An ActionLog representing the outcome of the execution.
        """
        pass
```

## 4. Domain Models (Input/Output)

-   **Input:** `ActionData` (from `plan_parser.md`)
-   **Output:** `ActionLog` (from `execution_report.md`)
