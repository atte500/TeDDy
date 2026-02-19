# Spec: Plan Execution Context

## 1. The Problem (The "Why")

The current `teddy` executor processes each action within a plan in complete isolation. This creates two significant operational failures:

1.  **Filesystem Isolation:** An `EXECUTE` action runs in a sandbox and cannot perceive any filesystem changes made by preceding `CREATE` or `EDIT` actions within the same plan. This makes it impossible to perform common developer workflows, such as creating a source file and immediately compiling or testing it, within a single, atomic plan.

2.  **Shell Command Fragility:** `EXECUTE` actions that contain complex, multi-line string arguments (e.g., `git commit -m "..."`) are frequently misinterpreted by the underlying shell, causing the command to fail. This is a recurring issue that makes the executor unreliable for version control tasks.

The goal of this initiative is to create a robust, unified execution context for each plan, solving both of these problems transparently.

## 2. Requirements & Constraints

### Functional Requirements

1.  **Transactional Filesystem Context:** All file modifications (`CREATE`, `EDIT`) within a given plan MUST be fully materialized and accessible to any subsequent `EXECUTE` action within that same plan.
2.  **Robust Command Execution:** The system must transparently handle multi-line arguments in shell commands, ensuring that commands like `git commit` execute reliably without modification to the plan's syntax.

### Non-Functional Requirements (Constraints)

1.  **Transparent Agent Experience:** The solution MUST be implemented within the executor's infrastructure. It must not require any new syntax, actions, or special considerations from the AI agent generating the plans. From the agent's perspective, the system should simply "work as expected."
2.  **Atomicity:** The execution of a plan should be atomic. If any action in the plan fails, any filesystem changes made by previous actions in that plan should be rolled back or discarded, leaving the user's workspace in its original state.

## 3. Core Use Cases

The final solution must successfully support the following scenarios without any special plan syntax:

### Use Case 1: Create and Execute a Test

-   **Given** a plan with two actions:
    1.  `CREATE` a new file `tests/test_new_feature.py`.
    2.  `EXECUTE` the command `pytest tests/test_new_feature.py`.
-   **Then** the `pytest` command must be able to find and execute the newly created test file successfully.

### Use Case 2: Create and Use a Configuration File

-   **Given** a plan with two actions:
    1.  `CREATE` a new file `config.json`.
    2.  `EXECUTE` a command `my-tool --config config.json`.
-   **Then** `my-tool` must be able to read the newly created configuration file.

### Use Case 3: Execute a Multi-line Git Commit

-   **Given** a plan with one action:
    1.  `EXECUTE` the command `git commit -m "feat: A great new feature\n\nThis is the detailed body of the commit message."`
-   **Then** a `git commit` must be created successfully with both a subject and a body.
