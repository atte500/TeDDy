# Application Core: Plan Service

**Language:** Python 3.9+
**Vertical Slice:** [Slice 01: Walking Skeleton](../../slices/01-walking-skeleton.md)

## 1. Purpose

The `PlanService` is the primary application service in the core logic. It acts as the orchestrator for the `RunPlanUseCase`. It is responsible for taking raw input, coordinating the domain models and outbound ports to execute the business logic, and returning the final result.

## 2. Port Implementations

*   **Implements Inbound Port:** [`RunPlanUseCase`](../ports/inbound/run_plan_use_case.md)

## 3. Dependencies

The `PlanService` will be initialized with the components it needs to perform its function.

*   **Factories:**
    *   [`ActionFactory`](../factories/action_factory.md) **Introduced in:** [Slice 03: Refactor Action Dispatching](../../slices/03-refactor-action-dispatching.md)
*   **Outbound Ports:**
    *   [`ShellExecutor`](../ports/outbound/shell_executor.md)
    *   [`FileSystemManager`](../ports/outbound/file_system_manager.md)

## 4. Implementation Strategy (Refactored)
**Related Slice:** [Slice 03: Refactor Action Dispatching](../../slices/03-refactor-action-dispatching.md)

The `PlanService` will be a class that is instantiated with its required dependencies via dependency injection. It uses an internal dispatch map to route action objects to the appropriate handler method, eliminating conditional logic.

```python
# High-level conceptual implementation

class PlanService(RunPlanUseCase):
    def __init__(
        self,
        action_factory: ActionFactory,
        shell_executor: ShellExecutor,
        file_system_manager: FileSystemManager
    ):
        self.action_factory = action_factory
        self.shell_executor = shell_executor
        self.file_system_manager = file_system_manager
        # The dispatch map is the core of the refactoring
        self.action_handlers = {
            ExecuteAction: self._handle_execute_action,
            CreateFileAction: self._handle_create_file_action,
        }

    def execute(self, plan_content: str) -> ExecutionReport:
        # ... implementation ...
```

### `execute(plan_content: str)` Method Logic

1.  **Start Report:** Create a new `ExecutionReport`.
2.  **Parse & Create Actions:**
    *   Use `pyyaml` to parse the `plan_content` string into a list of raw action dictionaries.
    *   For each raw action, call `self.action_factory.create_action()` to get a validated, concrete `Action` object. Handle any factory exceptions by creating a failure `ActionResult`.
3.  **Execute Actions:**
    *   Iterate through each successfully created `Action` object.
    *   Look up the action's class in the `self.action_handlers` dispatch map to find the correct handler method.
    *   If no handler is found, this is a programming error; create a failure `ActionResult`.
    *   Invoke the handler method with the action object (e.g., `handler(action)`).
    *   The handler method returns a complete `ActionResult`, which is appended to the report.
4.  **Finalize Report:**
    *   Calculate total duration and overall status.
    *   Return the `ExecutionReport`.

### Action Handler Methods

These private methods contain the logic for handling a single, specific action type. They are responsible for interacting with the correct outbound port and translating the result into an `ActionResult`.

*   `_handle_execute_action(action: ExecuteAction) -> ActionResult`:
    *   Calls `self.shell_executor.run(command=action.command)`.
    *   Builds and returns an `ActionResult` from the `CommandResult`.
*   `_handle_create_file_action(action: CreateFileAction) -> ActionResult`:
    *   Calls `self.file_system_manager.create_file(path=action.file_path, content=action.content)`.
    *   Catches specific exceptions from the port to determine success or failure.
    *   Builds and returns the corresponding `ActionResult`.
