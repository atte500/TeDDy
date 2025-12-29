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

## 1. Action & CommandResult

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
**Introduced in:** [Slice 01: Walking Skeleton](../slices/01-walking-skeleton.md)

An action that executes a shell command.

*   **Inherits from:** `Action`
*   **Attributes:**
    *   `command` (str): The shell command to execute.
*   **Invariants:**
    *   `command` must be a non-empty string.

---

### `CreateFileAction` (Entity)
**Status:** Implemented
**Introduced in:** [Slice 02: Implement `create_file` Action](../slices/02-create-file-action.md)

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
**Introduced in:** [Slice 04: Implement `read` Action](../slices/04-read-action.md)

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
**Introduced in:** [Slice 06: Implement `edit` Action](../slices/06-edit-action.md)

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
**Introduced in:** [Slice 10: Implement `chat_with_user` Action](../slices/10-chat-with-user-action.md)

An action that prompts the user with a question and captures their free-text response.

*   **Inherits from:** `Action`
*   **Attributes:**
    *   `prompt` (str): The question to display to the user.
*   **Invariants:**
    *   `prompt` must be a non-empty string.

---

### `ResearchAction` (Entity)
**Status:** Implemented
**Introduced in:** [Slice 11: Implement `research` action](../slices/11-research-action.md)

An action that performs a web search for a list of queries.

*   **Inherits from:** `Action`
*   **Attributes:**
    *   `queries` (list[str]): A list of search terms.
*   **Invariants:**
    *   `queries` must be a non-empty list of strings.

---

## 2. Plan (Aggregate Root)
**Status:** Implemented

Represents a full plan to be executed. It is the aggregate root for a collection of `Action` entities.

*   **Attributes:**
    *   `actions` (list[Action]): A list of `Action` objects.
*   **Invariants:**
    *   `actions` must be a list containing at least one `Action`.

---

## 3. ActionResult & ExecutionReport

### `ActionResult` (Value Object)
**Status:** Implemented

Represents the outcome of a single action's execution.

*   **Attributes:**
    *   `action` (Action): A copy of the concrete action object (e.g., `ExecuteAction`) that was executed.
    *   `status` (str): The outcome, one of `SUCCESS`, `FAILURE`, or `COMPLETED`.
    *   `output` (str | None): The captured stdout from the command.
    *   `error` (str | None): The captured stderr from the command.
*   **Invariants:**
    *   `status` must be one of `SUCCESS`, `FAILURE`, or `COMPLETED`.

### `ExecutionReport` (Entity)
**Status:** Implemented

A comprehensive report detailing the execution of an entire `Plan`.

*   **Attributes:**
    *   `run_summary` (dict): Top-level summary info (e.g., `status`, `start_time`, `duration`).
    *   `environment` (dict): Environment info (`os`, `cwd`).
    *   `action_logs` (list[ActionResult]): A list of results for each action executed.
*   **Invariants:**
    *   `action_logs` must be a list.

---

## 4. Search Result Value Objects
**Introduced in:** [Slice 11: Implement `research` action](../slices/11-research-action.md)

This hierarchy of value objects represents the structured results from a web search. They are immutable data containers.

### `SearchResult` (Value Object)
**Status:** Implemented

Represents a single search result item.

*   **Attributes:**
    *   `title` (str): The page title.
    *   `url` (str): The full URL.
    *   `snippet` (str): A descriptive snippet of the page content.

### `QueryResult` (Value Object)
**Status:** Implemented

Represents the collection of results for a single search query.

*   **Attributes:**
    *   `query` (str): The original search query string.
    *   `search_results` (list[SearchResult]): A list of individual search results.

### `SERPReport` (Value Object)
**Status:** Implemented

Represents the aggregated results for all queries in a `ResearchAction`. This is the object returned by the `IWebSearcher` port.

*   **Attributes:**
    *   `results` (list[QueryResult]): A list of results, one for each query.

---

## 5. Domain Exceptions

These are custom exceptions that represent specific business rule violations within the domain. They are used by outbound ports to communicate specific failure reasons to the application services.

### `FileAlreadyExistsError` (Exception)
**Status:** Implemented
**Introduced in:** [Slice 07: Update Action Failure Behavior](../slices/07-update-action-failure-behavior.md)

Raised by the `FileSystemManager` port when a `create_file` operation is attempted on a path that already exists.

*   **Purpose:** To allow the `PlanService` to specifically catch this failure and trigger the "read file content" fallback logic.
*   **Attributes:**
    *   `file_path` (str): The path of the file that already exists.

### `SearchTextNotFoundError` (Exception)
**Status:** Implemented
**Introduced in:** [Slice 07: Update Action Failure Behavior](../slices/07-update-action-failure-behavior.md)

Raised by the `FileSystemManager` port when an `edit_file` operation cannot find the specified `find` string within the target file.

*   **Purpose:** To allow the `PlanService` to specifically catch this failure and return the original file content as part of the failure report.
*   **Attributes:**
    *   `content` (str): The original, unmodified content of the file.

### `MultipleMatchesFoundError` (Exception)
**Status:** Implemented
**Introduced in:** [Slice 09: Enhance `edit` Action Safety](../slices/09-enhance-edit-action-safety.md)

Raised by the `FileSystemManager` port when an `edit_file` operation finds more than one occurrence of the `find` string.

*   **Purpose:** To prevent ambiguous edits and force the AI agent to provide a more specific `find` string.
*   **Attributes:**
    *   `content` (str): The original, unmodified content of the file.

### `WebSearchError` (Exception)
**Status:** Implemented
**Introduced in:** [Slice 11: Implement `research` action](../slices/11-research-action.md)

Raised by the `IWebSearcher` port when it fails to retrieve search results for any reason (e.g., network error, library failure).

*   **Purpose:** To allow the `PlanService` to catch this specific failure and create a descriptive `FAILED` `ActionResult`.
*   **Attributes:**
    *   `original_exception` (Exception | None): The underlying exception that caused the failure, for logging and debugging purposes.
---

## 6. Project Context
**Introduced in:** [./../slices/13-context-command.md](./../slices/13-context-command.md)

This section defines the objects related to gathering and representing the project's context for the AI.

### Aggregate: `ProjectContext`
- **Status:** Planned

A snapshot of the project's state, containing environmental information and the contents of key files.

#### Attributes
- `os_info`: string - Information about the operating system.
- `terminal_info`: string - Information about the terminal environment (e.g., shell type, version).
- `repo_tree`: string - A string representation of the repository's file structure.
- `file_contents`: map<string, FileContent> - A map where the key is the file path and the value is a `FileContent` object.

#### Behaviors
- `get_content(file_path)`: Retrieves the content of a specific file from the context.
- `add_file_content(file_path, content, status)`: Adds the content of a file to the context, along with its status ('found' or 'not_found').

#### Business Rules/Invariants
- The `repo_tree` must respect the ignore patterns from the project's `.gitignore` file.
- The `file_contents` map must include an entry for every file requested from both `context.yaml` and `permanent_context.yaml`.

---

### Value Object: `FileContent`
- **Status:** Planned

Represents the content of a single file within the project context, including a status indicating if it was successfully read.

#### Attributes
- `path`: string - The relative path to the file.
- `content`: string | null - The text content of the file, or null if not found.
- `status`: enum('found', 'not_found') - The status of the file read operation.
