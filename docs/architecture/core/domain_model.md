# Core Domain Model

**Language:** Python 3.9+ (using dataclasses)

This document defines the core entities for the `teddy` executor application. These objects represent the fundamental concepts and data structures of the system.

---

## Ubiquitous Language

*   **Plan:** A sequence of one or more Actions to be performed.
*   **Action:** A single, discrete step within a Plan.
*   **Execution Report:** A summary of the results of executing a Plan.
*   **Action Result:** The outcome (success, failure, output, error) of executing a single Action.

---

## 1. ActionType (Enum)
**Status:** Implemented

Enumerates the supported action types in the system.

*   `CREATE`, `READ`, `EDIT`, `EXECUTE`, `RESEARCH`, `PROMPT`, `PRUNE`, `INVOKE`, `RETURN`

---

## 2. Action & CommandResult

### `CommandResult` (Value Object)
**Status:** Implemented

Represents the captured result of an external command.

*   **Attributes:**
    *   `stdout` (str): The standard output from the command.
    *   `stderr` (str): The standard error from the command.
    *   `return_code` (int): The exit code of the command.
*   **Invariants:**
    *   `return_code` must be an integer.

### `Action` (Abstract Base Class)
**Status:** Implemented

Represents the contract for a single, executable step in a plan. This is an abstract concept; concrete actions will inherit from this class.

*   **Attributes:**
    *   `action_type` (str): A read-only property that returns the type of the action (e.g., "execute"). This will be hardcoded in each subclass.

---

### `ExecuteAction` (Entity)
**Status:** Implemented
**Modified in:** [Structured `execute` Action](../slices/executor/18-structured-execute-action.md)

An action that executes a shell command.

*   **Inherits from:** `Action`
*   **Attributes:**
    *   `command` (str): The shell command to execute.
    *   `cwd` (Optional[str]): An optional relative path specifying the working directory for the command. Defaults to `None`.
    *   `env` (Optional[Dict[str, str]]): An optional dictionary of environment variables to set for the command's process. Defaults to `None`.
*   **Invariants:**
    *   `command` must be a non-empty string.
    *   The `cwd` path is validated by the `IShellExecutor` adapter, not the domain object itself.

---

### `CreateFileAction` (Entity)
**Status:** Implemented

An action that creates a new file.

*   **Inherits from:** `Action`
*   **Attributes:**
    *   `file_path` (str): The path where the new file will be created.
    *   `content` (str): The content to write into the new file. Defaults to an empty string.
*   **Invariants:**
    *   `file_path` must be a non-empty string.

---

### `ParsePlanAction` (Entity)
**Status:** Implemented

A synthetic action used internally to represent the plan parsing step in execution reports. It does not correspond to a user-defined action in a YAML plan.

*   **Inherits from:** `Action`
*   **Attributes:**
    *   None.

---

### `ReadAction` (Entity)
**Status:** Implemented

An action that reads the content of a local file or a remote URL.

*   **Inherits from:** `Action`
*   **Attributes:**
    *   `source` (str): The path to the local file or the remote URL to be read.
*   **Invariants:**
    *   `source` must be a non-empty string.
*   **Behaviors:**
    *   `is_remote()`: Returns `True` if the `source` starts with `http://` or `https://`.

---

### `EditAction` (Entity)
**Status:** Implemented

An action that finds and replaces content within an existing file.

*   **Inherits from:** `Action`
*   **Attributes:**
    *   `file_path` (str): The path to the file to be modified.
    *   `find` (str): The exact string of content to search for.
    *   `replace` (str): The string that will replace the `find` content.
*   **Invariants:**
    *   `file_path` must be a non-empty string.
*   **Behaviors:**
    *   An empty `find` string is permissible and signals that the entire file content should be replaced with the `replace` content.

---

### `ChatWithUserAction` (Entity)
**Status:** Implemented

An action that prompts the user with a question and captures their free-text response.

*   **Inherits from:** `Action`
*   **Attributes:**
    *   `prompt` (str): The question to display to the user.
*   **Invariants:**
    *   `prompt` must be a non-empty string.

---

### `ResearchAction` (Entity)
**Status:** Implemented

An action that performs a web search for a list of queries.

*   **Inherits from:** `Action`
*   **Attributes:**
    *   `queries` (list[str]): A list of search terms.
*   **Invariants:**
    *   `queries` must be a non-empty list of strings.

---

## 2. Plan (Aggregate Root)
**Status:** Implemented

Represents a full plan to be executed. It is the aggregate root for a collection of `ActionData` objects.

**Implementation Logic:**
- **Mutability:** Unlike the immutable `ExecutionReport`, the `Plan` and its `ActionData` are **mutable** (unfrozen). This allows primary adapters (like the TUI Reviewer) to modify plan parameters and selection state in-memory before execution without the overhead of deep copying and re-validation.

*   **Attributes:**
    *   `title` (str): The plan's title.
    *   `rationale` (str): The AI's explanation for the plan.
    *   `actions` (list[ActionData]): A list of `ActionData` objects.
*   **Invariants:**
    *   `actions` must be a list containing at least one action.

---

## 3. ActionResult & ExecutionReport

### `ActionResult` (Value Object)
**Status:** Implemented

Represents the outcome of a single action's execution.

*   **Attributes:**
    *   `action` (Action): A copy of the concrete action object (e.g., `ExecuteAction`) that was executed.
    *   `status` (str): The outcome, one of `SUCCESS`, `FAILURE`, `COMPLETED`, or `SKIPPED`.
    *   `output` (str | None): The captured stdout from the command.
    *   `error` (str | None): The captured stderr from the command.
    *   `reason` (str | None): An optional reason, typically for a `SKIPPED` status.
*   **Invariants:**
    *   `status` must be one of `SUCCESS`, `FAILURE`, `COMPLETED`, or `SKIPPED`.

### `ExecutionReport` (Entity)
**Status:** Implemented

A comprehensive report detailing the execution of an entire `Plan`.

*   **Attributes:**
    *   `run_summary` (RunSummary): Top-level summary info (e.g., `status`, `start_time`, `duration`).
    *   `plan_title` (str | None): The title of the plan.
    *   `rationale` (str | None): The rationale from the plan.
    *   `original_actions` (list[ActionData]): A copy of the actions as proposed in the plan.
    *   `action_logs` (list[ActionLog]): A list of results for each action executed.
    *   `validation_result` (list[str] | None): A list of error messages if validation failed.
    *   `failed_resources` (dict[str, str] | None): Content of relevant files if execution or validation failed.

---


---

## 5. Domain Exceptions

These are custom exceptions that represent specific business rule violations within the domain. They are used by outbound ports to communicate specific failure reasons to the application services.

### `FileAlreadyExistsError` (Exception)
**Status:** Implemented

Raised by the `FileSystemManager` port when a `create_file` operation is attempted on a path that already exists.

*   **Purpose:** To allow the `PlanService` to specifically catch this failure and trigger the "read file content" fallback logic.
*   **Attributes:**
    *   `file_path` (str): The path of the file that already exists.

### `SearchTextNotFoundError` (Exception)
**Status:** Implemented

Raised by the `FileSystemManager` port when an `edit_file` operation cannot find the specified `find` string within the target file.

*   **Purpose:** To allow the `PlanService` to specifically catch this failure and return the original file content as part of the failure report.
*   **Attributes:**
    *   `content` (str): The original, unmodified content of the file.

### `MultipleMatchesFoundError` (Exception)
**Status:** Implemented

Raised by the `FileSystemManager` port when an `edit_file` operation finds more than one occurrence of the `find` string.

*   **Purpose:** To prevent ambiguous edits and force the AI agent to provide a more specific `find` string.
*   **Attributes:**
    *   `content` (str): The original, unmodified content of the file.

### `WebSearchError` (Exception)
**Status:** Implemented

Raised by the `IWebSearcher` port when it fails to retrieve search results for any reason (e.g., network error, library failure).

*   **Purpose:** To allow the `PlanService` to catch this specific failure and create a descriptive `FAILED` `ActionResult`.
*   **Attributes:**
    *   `original_exception` (Exception | None): The underlying exception that caused the failure, for logging and debugging purposes.
---

## 6. Project Context Aggregate

This section defines the objects related to gathering and representing the project's context for the AI.

### `FileContext` (Value Object)
**Status:** Implemented

Represents the content and status of a single file requested for context.

*   **Attributes:**
    *   `file_path` (str): The path to the file.
    *   `content` (str | None): The content of the file, or `None` if it could not be read.
    *   `status` (str): The read status, one of "found" or "not_found".
*   **Invariants:**
    *   `status` must be either "found" or "not_found".
