# Application Core: Plan Service

**Language:** Python 3.9+
**Vertical Slice:** [Slice 01: Walking Skeleton](../../slices/01-walking-skeleton.md)

## 1. Purpose

The `PlanService` is the primary application service in the core logic. It acts as the orchestrator for the `RunPlanUseCase`. It is responsible for taking raw input, coordinating the domain models and outbound ports to execute the business logic, and returning the final result.

## 2. Port Implementations

*   **Implements Inbound Port:** [`RunPlanUseCase`](../ports/inbound/run_plan_use_case.md)

## 3. Dependencies (Outbound Ports)

The `PlanService` will be initialized with the outbound ports it needs to perform its function.

*   **Uses Outbound Port:** [`ShellExecutor`](../ports/outbound/shell_executor.md)

## 4. Implementation Strategy

The `PlanService` will be a class that is instantiated with its required dependencies (the outbound ports) via dependency injection in its constructor.

```python
# High-level conceptual implementation

class PlanService(RunPlanUseCase):

    def __init__(self, shell_executor: ShellExecutor):
        self.shell_executor = shell_executor

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
    *   For an `execute` action:
        a.  Call `self.shell_executor.run(command)`.
        b.  Receive the `CommandResult` from the port.
        c.  Create a corresponding `ActionResult` (SUCCESS or FAILURE) based on the `return_code`.
        d.  Add the `ActionResult` to the report's `action_logs`.
4.  **Finalize Report:**
    *   Calculate the total duration.
    *   Determine the overall `status` (FAILURE if any action failed, otherwise SUCCESS).
    *   Update the `run_summary`.
    *   Return the completed `ExecutionReport`.
