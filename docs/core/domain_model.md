# Core Domain Model

**Language:** Python 3.9+ (using dataclasses)
**Vertical Slice:** [Slice 01: Walking Skeleton](../slices/01-walking-skeleton.md)

This document defines the core entities for the `teddy` executor application. These objects represent the fundamental concepts and data structures of the system.

---

## Ubiquitous Language

*   **Plan:** A sequence of one or more Actions to be performed.
*   **Action:** A single, discrete step within a Plan.
*   **Execution Report:** A summary of the results of executing a Plan.
*   **Action Result:** The outcome (success, failure, output, error) of executing a single Action.

---

## 1. Action & CommandResult

### `CommandResult` (Value Object)

Represents the captured result of an external command.

*   **Attributes:**
    *   `stdout` (str): The standard output from the command.
    *   `stderr` (str): The standard error from the command.
    *   `return_code` (int): The exit code of the command.
*   **Invariants:**
    *   `return_code` must be an integer.

### `Action` (Entity)

Represents a single step in a plan. For the Walking Skeleton, this will only encapsulate an `execute` command.

*   **Attributes:**
    *   `action_type` (str): The type of action (e.g., "execute"). Fixed to "execute" for this slice.
    *   `params` (dict): A dictionary of parameters for the action. For `execute`, this will contain a `command` key.
*   **Invariants:**
    *   `action_type` must be a non-empty string.
    *   `params` must be a dictionary.
    *   For `action_type == "execute"`, `params` must contain a non-empty string value for the key `command`.

---

## 2. Plan (Aggregate Root)

Represents a full plan to be executed. It is the aggregate root for a collection of `Action` entities.

*   **Attributes:**
    *   `actions` (list[Action]): A list of `Action` objects.
*   **Invariants:**
    *   `actions` must be a list containing at least one `Action`.

---

## 3. ActionResult & ExecutionReport

### `ActionResult` (Value Object)

Represents the outcome of a single action's execution.

*   **Attributes:**
    *   `action` (Action): A copy of the action that was executed.
    *   `status` (str): The outcome, one of `SUCCESS`, `FAILURE`.
    *   `output` (str | None): The captured stdout from the command.
    *   `error` (str | None): The captured stderr from the command.
*   **Invariants:**
    *   `status` must be either `SUCCESS` or `FAILURE`.

### `ExecutionReport` (Entity)

A comprehensive report detailing the execution of an entire `Plan`.

*   **Attributes:**
    *   `run_summary` (dict): Top-level summary info (e.g., `status`, `start_time`, `duration`).
    *   `environment` (dict): Environment info (`os`, `cwd`).
    *   `action_logs` (list[ActionResult]): A list of results for each action executed.
*   **Invariants:**
    *   `action_logs` must be a list.
