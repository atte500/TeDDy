# Application Core: Plan Service

**Status:** Refactoring
**Language:** Python 3.9+
**Vertical Slice:** [Slice 01: Walking Skeleton](../../slices/executor/01-walking-skeleton.md)
**Modified in:** [Structured `execute` Action](../../slices/executor/18-structured-execute-action.md)

## 1. Purpose

The `PlanService` is the primary application service in the core logic. It acts as the orchestrator for the `RunPlanUseCase`. It is responsible for taking raw input, coordinating the domain models and outbound ports to execute the business logic, and returning the final result. It also enforces application-level security policies, such as sandboxing file system access.

## 2. Port Implementations

*   **Implements Inbound Port:** [`RunPlanUseCase`](../ports/inbound/run_plan_use_case.md)

## 3. Dependencies

The `PlanService` will be initialized with the components it needs to perform its function.

*   **Factories:**
    *   [`ActionFactory`](../services/action_factory.md) **Introduced in:** [Slice 03: Refactor Action Dispatching](../../slices/03-refactor-action-dispatching.md)
*   **Outbound Ports:**
        *   [`IShellExecutor`](../ports/outbound/shell_executor.md)
        *   [`FileSystemManager`](../ports/outbound/file_system_manager.md)
        *   [`WebScraper`](../ports/outbound/web_scraper.md) **Introduced in:** [Slice 04: Implement `read` Action](../../slices/04-read-action.md)
        *   [`IUserInteractor`](../ports/outbound/user_interactor.md) **Introduced in:** [Slice 10: Implement `chat_with_user` Action](../../slices/10-chat-with-user-action.md)
        *   [`IWebSearcher`](../ports/outbound/web_searcher.md) **Introduced in:** [Slice 11: Implement `research` action](../../slices/11-research-action.md)

## 4. Implementation Strategy (Refactored)
**Related Slice:** [Slice 08: Refactor Action Dispatching](../../slices/08-refactor-action-dispatching.md)

The `PlanService` is a class instantiated with its required dependencies. It uses an internal dispatch map (`self.action_handlers`) to route action objects to the appropriate handler method, eliminating conditional logic and making the system more scalable.

```python
# High-level conceptual implementation

class PlanService(RunPlanUseCase):
    def __init__(
        self,
        shell_executor: IShellExecutor,
        file_system_manager: FileSystemManager,
        action_factory: ActionFactory,
        web_scraper: WebScraper,
        user_interactor: IUserInteractor,
        web_searcher: IWebSearcher,
    ):
        self.shell_executor = shell_executor
        self.file_system_manager = file_system_manager
        self.action_factory = action_factory
        self.web_scraper = web_scraper
        self.user_interactor = user_interactor
        self.web_searcher = web_searcher
        # The dispatch map is the core of the refactoring
        self.action_handlers = {
            ExecuteAction: self._handle_execute,
            CreateFileAction: self._handle_create_file,
            ReadAction: self._handle_read,
            EditAction: self._handle_edit,
            ChatWithUserAction: self._handle_chat_with_user,
            ResearchAction: self._handle_research,
        }

    def execute(self, plan_content: str, auto_approve: bool = False) -> ExecutionReport:
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

### `execute(plan_content: str, auto_approve: bool = False)` Method Logic
**Status:** Refactoring
**Updated in:** [Slice 19: Unified `execute` Command & Interactive Approval](../../slices/executor/19-unified-execute-command.md)

1.  **Start Report:** Create a new `ExecutionReport`.
2.  **Parse & Create Actions:**
    *   Use `pyyaml` to parse the `plan_content` string.
    *   For each raw action, call `self.action_factory.create_action()` to get a validated, concrete `Action` object.
    *   Catches parsing and validation errors and creates a `FAILURE` `ActionResult`.
3.  **Execute Actions:**
    *   Iterate through each successfully created `Action` object.
    *   **Approval Check:**
        *   If `auto_approve` is `False`, call `self.user_interactor.confirm_action()` with a descriptive prompt for the current action.
        *   If the user denies the action (returns `False`), create a `SKIPPED` `ActionResult`, capture the optional reason, append it to the report, and continue to the next action.
    *   **Dispatch:**
        *   If the action is approved (or if `auto_approve` is `True`), invoke `_execute_single_action(action)`, which looks up and executes the correct handler method.
        *   The handler method returns a complete `ActionResult`, which is appended to the report.
4.  **Finalize Report:**
    *   Calculate total duration and overall status.
    *   Return the `ExecutionReport`.

### Action Handler Methods

These private methods contain the logic for handling a single, specific action type. They are responsible for interacting with the correct outbound port and translating the result into an `ActionResult`.

*   `_handle_execute(action: ExecuteAction) -> ActionResult`:
    *   The method wraps the call to the shell executor in a `try...except` block.
    *   **`try` block:**
        *   Calls `self.shell_executor.execute(command=action.command, cwd=action.cwd, env=action.env)`. The `ShellAdapter` is now responsible for validating the `cwd` path before execution.
        *   Builds and returns an `ActionResult` from the returned `CommandResult`.
    *   **`except (ValueError, FileNotFoundError) as e` block:**
        *   Catches validation errors (`ValueError`) or execution errors (`FileNotFoundError`) raised by the adapter.
        *   Returns a `FAILURE` `ActionResult` with the error message from the exception.
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

*   `_handle_edit_action(action: EditAction) -> ActionResult`: **(Updated in: [Slice 09: Enhance `edit` Action Safety](../../slices/09-enhance-edit-action-safety.md))**
    *   The method uses a `try...except` block to orchestrate the edit operation and handle specific failure modes.
    *   **`try` block:**
        *   Calls `self.file_system_manager.edit_file(...)`.
        *   If successful, returns a `COMPLETED` `ActionResult`.
    *   **`except SearchTextNotFoundError as e` block:**
        *   Catches the failure for zero matches.
        *   Returns a `FAILED` `ActionResult` with an error message and the original file content from `e.content`.
    *   **`except MultipleMatchesFoundError as e` block:**
        *   Catches the failure for multiple matches.
        *   Returns a `FAILED` `ActionResult` with an error message and the original file content from `e.content`.
    *   **`except FileNotFoundError as e` block:**
        *   Catches the error if the target file does not exist.
        *   Returns a `FAILED` `ActionResult` with a descriptive error message.

*   `_handle_chat_with_user(action: ChatWithUserAction) -> ActionResult`:
    *   Calls `self.user_interactor.ask_question(prompt=action.prompt_text)`.
    *   Catches any exceptions from the port and returns a `FAILED` `ActionResult`.
    *   On success, builds and returns a `SUCCESS` `ActionResult` with the user's response in the `output` field.

*   `_handle_research(action: ResearchAction) -> ActionResult`:
    *   The method will use a `try...except` block.
    *   **`try` block:**
        *   Calls `self.web_searcher.search(queries=action.queries)`.
        *   The returned `SERPReport` object is serialized into a JSON string. A helper/utility function should be used for this serialization to ensure consistency.
        *   Builds and returns a `SUCCESS` `ActionResult` with the JSON string in the `output` field.
    *   **`except WebSearchError as e` block:**
        *   Catches the specific exception from the port.
        *   Builds and returns a `FAILED` `ActionResult` with a descriptive error message from the exception `e`.
    *   **`except Exception` block:**
        *   Catches any other unexpected exceptions and returns a generic `FAILED` `ActionResult`.
