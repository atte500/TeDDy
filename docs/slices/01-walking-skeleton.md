# Vertical Slice 01: Walking Skeleton

This slice implements the simplest possible end-to-end flow of the `teddy` executor: reading a basic plan from stdin, executing a single command, and printing a report to stdout.

### 1. Business Goal

As a user, I want to execute a simple, non-interactive plan containing a single `execute` action so that I can verify the core parsing and execution mechanics of the tool are working.

### 2. Acceptance Criteria (Scenarios)

*   **Scenario 1: Successful Execution**
    *   **Given:** I have a valid YAML plan containing a single `execute` action that runs `echo "hello world"`.
    *   **When:** I pipe this plan into the `teddy` command.
    *   **Then:** The command should exit with a status code of 0.
    *   **And:** The final execution report printed to stdout should show a `SUCCESS` status for the action.
    *   **And:** The `Output` block for the action in the report should contain "hello world".

*   **Scenario 2: Failed Execution**
    *   **Given:** I have a valid YAML plan containing a single `execute` action that runs a non-existent command like `nonexistentcommand123`.
    *   **When:** I pipe this plan into the `teddy` command.
    *   **Then:** The command should exit with a status code of 0 (the tool itself ran successfully).
    *   **And:** The final execution report printed to stdout should show a `FAILURE` status for the action.
    *   **And:** The `Error` block for the action in the report should contain text indicating the command was not found.

### 3. Interaction Sequence

1.  User invokes `teddy` via a shell pipe (e.g., `echo '...' | teddy`).
2.  The `CLI Adapter` reads the complete YAML string from `stdin`.
3.  The `CLI Adapter` calls the `RunPlanUseCase` (inbound port) with the YAML content.
4.  The `Application Core` parses the YAML into a `Plan` domain object.
5.  The `Application Core` iterates through the actions in the `Plan`.
6.  For the `execute` action, the `Application Core` calls the `ShellExecutor` (outbound port).
7.  The `ShellAdapter` (implementation of `ShellExecutor`) executes the command as a subprocess, capturing stdout, stderr, and the return code.
8.  The `ShellAdapter` returns the result to the `Application Core`.
9.  The `Application Core` builds an `ExecutionReport` domain object.
10. The `Application Core` returns the `ExecutionReport` to the `CLI Adapter`.
11. The `CLI Adapter` formats the report as Markdown and prints it to `stdout`.

### 4. Scope of Work (Components)

-   **Domain Model (`src/teddy/core/domain`):**
    -   [ ] `Plan`: Represents a list of actions.
    -   [ ] `Action`: Represents a single action to be executed (initially, only `execute`).
    -   [ ] `ExecutionReport`: Represents the results of a plan execution.
-   **Inbound Ports (`src/teddy/core/ports/inbound`):**
    -   [ ] `RunPlanUseCase`: A port with one method, `execute(plan_content: str) -> ExecutionReport`.
-   **Outbound Ports (`src/teddy/core/ports/outbound`):**
    -   [ ] `ShellExecutor`: A port with one method, `run(command: str) -> CommandResult`.
-   **Application Core (`src/teddy/core/services`):**
    -   [ ] `PlanService`: Implements the `RunPlanUseCase`.
-   **Inbound Adapters (`src/teddy/adapters/inbound`):**
    -   [ ] `CLI`: The main Typer application entry point (`main.py`) that reads from stdin.
-   **Outbound Adapters (`src/teddy/adapters/outbound`):**
    -   [ ] `ShellAdapter`: Implements the `ShellExecutor` using Python's `subprocess` module.
