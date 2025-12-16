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
        *   [`WebScraper`](../ports/outbound/web_scraper.md) **Introduced in:** [Slice 04: Implement `read` Action](../../slices/04-read-action.md)

## 4. Implementation Strategy (Refactored)
**Related Slice:** [Slice 08: Refactor Action Dispatching](../../slices/08-refactor-action-dispatching.md)

The `PlanService` is a class instantiated with its required dependencies. It uses an internal dispatch map (`self.action_handlers`) to route action objects to the appropriate handler method, eliminating conditional logic and making the system more scalable.

```python
# High-level conceptual implementation

class PlanService(RunPlanUseCase):
    def __init__(
        self,
        shell_executor: ShellExecutor,
        file_system_manager: FileSystemManager,
        action_factory: ActionFactory,
        web_scraper: WebScraper,
    ):
        self.shell_executor = shell_executor
        self.file_system_manager = file_system_manager
        self.action_factory = action_factory
        self.web_scraper = web_scraper
        # The dispatch map is the core of the refactoring
        self.action_handlers = {
            ExecuteAction: self._handle_execute,
            CreateFileAction: self._handle_create_file,
            ReadAction: self._handle_read,
            EditAction: self._handle_edit,
        }

    def execute(self, plan_content: str) -> ExecutionReport:
        # ... implementation ...

    def _execute_single_action(self, action: Action) -> ActionResult:
        """Executes one action by looking up its handler in the dispatch map."""
        handler = self.action_handlers.get(type(action))
        if handler:
            return handler(action)

        return ActionResult(
            action=action,
            status="FAILURE",
            error=f"Unhandled action type: {type(action).__name__}",
        )
```

### `execute(plan_content: str)` Method Logic

1.  **Start Report:** Create a new `ExecutionReport`.
2.  **Parse & Create Actions:**
    *   Use `pyyaml` to parse the `plan_content` string.
    *   For each raw action, call `self.action_factory.create_action()` to get a validated, concrete `Action` object.
    *   Catches parsing and validation errors and creates a `FAILURE` `ActionResult`.
3.  **Execute Actions:**
    *   Iterate through each successfully created `Action` object.
    *   Invoke `_execute_single_action(action)`, which looks up the action's class in the `self.action_handlers` dispatch map to find and execute the correct handler method.
    *   The handler method returns a complete `ActionResult`, which is appended to the report.
4.  **Finalize Report:**
    *   Calculate total duration and overall status.
    *   Return the `ExecutionReport`.

### Action Handler Methods

These private methods contain the logic for handling a single, specific action type. They are responsible for interacting with the correct outbound port and translating the result into an `ActionResult`.

*   `_handle_execute_action(action: ExecuteAction) -> ActionResult`:
    *   Calls `self.shell_executor.run(command=action.command)`.
    *   Builds and returns an `ActionResult` from the `CommandResult`.
*   `_handle_create_file_action(action: CreateFileAction) -> ActionResult`: **(Updated in: [Slice 07: Update Action Failure Behavior](../../slices/07-update-action-failure-behavior.md))**
    *   The method will use a `try...except` block.
    *   **`try` block:**
        *   Calls `self.file_system_manager.create_file(path=action.file_path, content=action.content)`.
        *   If successful, builds and returns a `SUCCESS` `ActionResult`.
    *   **`except FileAlreadyExistsError as e` block:**
        *   Catches the specific exception from the port.
        *   Calls `self.file_system_manager.read_file(path=e.file_path)` to get the existing content.
        *   Builds and returns a `FAILED` `ActionResult`, placing the retrieved content into the `output` field.
    *   **`except Exception` block:**
        *   Catches any other unexpected exceptions and returns a generic `FAILED` `ActionResult`.
*   `_handle_read_action(action: ReadAction) -> ActionResult`:
    *   Inspects `action.source` to determine if it is a URL (starts with `http://` or `https://`).
    *   **If URL:** Calls `self.web_scraper.get_content(url=action.source)`.
    *   **If file path:** Calls `self.file_system_manager.read_file(path=action.source)`.
    *   Catches specific exceptions from either port (e.g., `FileNotFoundError`, `WebContentError`) to create a failure `ActionResult` with a descriptive error message.
    *   On success, builds and returns an `ActionResult` with the file/page content in the `output` field.

*   `_handle_edit_action(action: EditAction) -> ActionResult`: **(Updated in: [Slice 07: Update Action Failure Behavior](../../slices/07-update-action-failure-behavior.md))**
    *   The method will use a `try...except` block.
    *   **`try` block:**
        *   Calls `self.file_system_manager.edit_file(path=action.file_path, find=action.find, replace=action.replace)`.
        *   If successful, builds and returns a `COMPLETED` `ActionResult`.
    *   **`except SearchTextNotFoundError as e` block:**
        *   Catches the specific exception from the port.
        *   Builds and returns a `FAILED` `ActionResult` with an appropriate error message and the file's original content (retrieved from the exception object) in the `output` field.
    *   **`except FileNotFoundError as e` block:**
        *   Catches the standard file not found error and returns a `FAILED` `ActionResult` with a descriptive error message.
    *   **`except Exception` block:**
        *   Catches any other unexpected exceptions and returns a generic `FAILED` `ActionResult`.
