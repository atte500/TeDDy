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

### `Action` (Abstract Base Class)

Represents the contract for a single, executable step in a plan. This is an abstract concept; concrete actions will inherit from this class.

*   **Attributes:**
    *   `action_type` (str): A read-only property that returns the type of the action (e.g., "execute"). This will be hardcoded in each subclass.

---

### `ExecuteAction` (Entity)
**Introduced in:** [Slice 01: Walking Skeleton](../slices/01-walking-skeleton.md)

An action that executes a shell command.

*   **Inherits from:** `Action`
*   **Attributes:**
    *   `command` (str): The shell command to execute.
    *   `cwd` (str | None): The working directory for the command. Defaults to the current directory.
    *   `background` (bool): Whether to run the command in the background. Defaults to `False`.
    *   `timeout` (int | None): Timeout in seconds for the command.
*   **Invariants:**
    *   `command` must be a non-empty string.

---

### `CreateFileAction` (Entity)
**Introduced in:** [Slice 02: Implement `create_file` Action](../slices/02-create-file-action.md)

An action that creates a new file.

*   **Inherits from:** `Action`
*   **Attributes:**
    *   `file_path` (str): The path where the new file will be created.
    *   `content` (str): The content to write into the new file. Defaults to an empty string.
*   **Invariants:**
    *   `file_path` must be a non-empty string.

---

### `ReadAction` (Entity)
**Introduced in:** [Slice 04: Implement `read` Action](../slices/04-read-action.md)

An action that reads the content of a local file or a remote URL.

*   **Inherits from:** `Action`
*   **Attributes:**
    *   `source` (str): The path to the local file or the remote URL to be read.
*   **Invariants:**
    *   `source` must be a non-empty string.

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
    *   `action` (Action): A copy of the concrete action object (e.g., `ExecuteAction`) that was executed.
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
