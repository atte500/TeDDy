# RCA: `AssertionError` due to Misconfigured Mock Factory

## 1. Summary
The system experienced an `AssertionError: Expected 'run' to be called once. Called 0 times.` when running the unit test `tests/unit/core/services/test_plan_service.py::test_plan_service_parses_and_executes_plan`. This occurred after refactoring `PlanService` to use an `ActionFactory`.

## 2. Investigation
The investigation confirmed the primary hypothesis that the mock `ActionFactory` in the unit test was not correctly configured.

1.  **Hypothesis 1: Mock Factory Return Value is Misconfigured (Confirmed)**
    *   **Description:** The test created a `MagicMock` for the `ActionFactory` but did not specify what its `create_action` method should return. By default, a `MagicMock` method call returns a new, generic `MagicMock` instance. This returned mock lacked the `action_type` attribute required by the `PlanService`'s dispatch logic (`if action.action_type == "execute":`).
    *   **Evidence:** The spike at `spikes/debug/01-verify-mock-return-value/check_mock_behavior.py` successfully reproduced the issue in isolation and demonstrated the required fix. The unconfigured mock failed to trigger the dispatch logic, while the correctly configured mock succeeded.

## 3. Root Cause
The root cause was an incomplete test setup. The mock for the `ActionFactory` dependency was created but not configured. The `PlanService`'s internal logic relies on the objects returned by the factory to have specific attributes (`action_type`, `params`). When the unconfigured mock returned a generic mock object without these attributes, the conditional logic to call the `shell_executor` was never triggered, leading to the assertion failure.

## 4. Recommended Action
The test `test_plan_service_parses_and_executes_plan` must be updated to configure the return value of the `mock_action_factory.create_action` method. It should return an object (e.g., a `Mock` or `SimpleNamespace`) that has the `action_type` and `params` attributes matching the test's input plan.

A verifier script demonstrating the recommended implementation is located at `spikes/debug/solution_verifier.py`.
