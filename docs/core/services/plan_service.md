# Application Core: Plan Service

**Language:** Python 3.9+
**Vertical Slice:** [Slice 01: Walking Skeleton](../../slices/01-walking-skeleton.md)

## 1. Purpose

The `PlanService` is the primary application service in the core logic. It acts as the orchestrator for the `RunPlanUseCase`. It is responsible for taking raw input, coordinating the domain models and outbound ports to execute the business logic, and returning the final result.

## 2. Port Implementations

*   **Implements Inbound Port:** [`RunPlanUseCase`](../ports/inbound/run_plan_use_case.md)

## 3. Dependencies (Outbound Ports)

The `PlanService` will be initialized with the outbound ports it needs to perform its function.

*   **Uses Outbound Port:** [`ShellExecutor`](../ports/outbound/shell_executor.md) **Introduced in:** [Slice 01: Walking Skeleton](../../slices/01-walking-skeleton.md)
*   **Uses Outbound Port:** [`FileSystemManager`](../ports/outbound/file_system_manager.md) **Introduced in:** [Slice 02: Implement `create_file` Action](../../slices/02-create-file-action.md)

## 4. Implementation Strategy

The `PlanService` will be a class that is instantiated with its required dependencies (the outbound ports) via dependency injection in its constructor.

```python
# High-level conceptual implementation

class PlanService(RunPlanUseCase):

    def __init__(
        self,
        shell_executor: ShellExecutor,
        file_system_manager: FileSystemManager
    ):
        self.shell_executor = shell_executor
        self.file_system_manager = file_system_manager

    def execute(self, plan_content: str) -> ExecutionReport:
        # ... implementation ...
```

### `execute(plan_content: str)` Method Logic

1.  **Start Report:** Create a new `ExecutionReport` object and record the start time and environment details.
2.  **Parse Input:**
    *   Use the `pyyaml` library to parse the `plan_content` string.
    *   If parsing fails, create a failure `ActionResult`, add it to the report, finalize the report summary, and return it immediately.
    *   If parsing succeeds, validate the structure and create `Action` and `Plan` domain objects.
3.  **Execute Actions:**
    *   Iterate through each `Action` in the `Plan`.
    *   **For an `execute` action:**
        a.  Call `self.shell_executor.run(command)`.
        b.  Receive the `CommandResult` from the port.
        c.  Create a corresponding `ActionResult` and add it to the report.
    *   **For a `create_file` action:** (**Introduced in:** [Slice 02: Implement `create_file` Action](../../slices/02-create-file-action.md))
        a.  Extract `file_path` and `content` from the action's `params`.
        b.  Call `self.file_system_manager.create_file(path=file_path, content=content)`.
        c.  The port will raise a specific exception (e.g., `FileExistsError`) on failure.
        d.  Create a corresponding `ActionResult` (SUCCESS or FAILURE) based on the outcome.
        e.  Add the `ActionResult` to the report.
4.  **Finalize Report:**
    *   Calculate the total duration.
    *   Determine the overall `status` (FAILURE if any action failed, otherwise SUCCESS).
    *   Update the `run_summary`.
    *   Return the completed `ExecutionReport`.
