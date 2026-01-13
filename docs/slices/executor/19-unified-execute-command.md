# Vertical Slice: Unified `execute` Command & Interactive Approval

**Source Brief:** User Request

## 1. Business Goal

To streamline the AI-assisted development workflow by creating a single `teddy execute` command that can run plans from either the clipboard or a file. This will be paired with a step-by-step interactive approval mechanism to give the user full, safe control over every action performed.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: Execute Plan from Clipboard with Interactive Approval
- **Given** I have a valid plan YAML in my system clipboard.
- **When** I run `teddy execute` in my terminal.
- **Then** the application should prompt me for approval (`y/n`) before executing each action.
- **And** if I approve, the action is executed.
- **And** if I deny, the action is skipped.

*Example:*
```
> teddy execute
Action 1/3: create_file (path: 'src/main.py')
Approve? (y/n): y
...
Action 2/3: execute (command: 'python src/main.py')
Approve? (y/n): n
Reason for skipping (optional): I want to review the file first.
...
Action 3/3: read (path: 'output.txt')
Approve? (y/n): y
```

### Scenario 2: Execute Plan from File with Auto-Approval
- **Given** a file named `plan.yaml` contains a valid plan.
- **When** I run `teddy execute plan.yaml --yes`.
- **Then** the application should execute all actions in the plan without prompting for approval.

### Scenario 3: Skipping an Action
- **Given** I am prompted to approve an action.
- **When** I respond with `n`.
- **And** I provide the optional reason "Manual check needed".
- **Then** the final execution report must show that action with a `SKIPPED` status and include the reason "Manual check needed".

## 3. Architectural Changes

- **Inbound CLI Adapter:** Refactor `main.py` to consolidate execution logic into a single `execute` command that handles clipboard/file input and an `--yes` flag.
- **IUserInteractor (Port):** Add a new method to the interface to handle the `y/n` confirmation and the optional reason prompt.
- **ConsoleInteractorAdapter (Adapter):** Implement the new confirmation method.
- **PlanService (Application Service):** Integrate the approval loop into the main `execute` method, calling the `IUserInteractor` before dispatching each action.
- **Dependency:** Add `pyperclip` to the `executor` package's `pyproject.toml`.

## 4. Interaction Sequence

1.  User runs `teddy execute [PLAN_FILE] [--yes]`.
2.  The **CLI Adapter** in `main.py` is invoked.
3.  It determines the plan source (clipboard or file) and reads the content.
4.  It determines the approval mode (interactive or auto-approve from the `--yes` flag).
5.  It calls the `PlanService.execute()` method, passing the plan content and the approval mode flag.
6.  Inside `PlanService`, for each action in the plan:
    a. If in interactive mode, it calls `IUserInteractor.confirm_action()`.
    b. The **ConsoleInteractorAdapter** prompts the user for `y/n` and an optional reason.
    c. If the user approves, `PlanService` dispatches the action for execution.
    d. If the user denies, `PlanService` logs the action as `SKIPPED` with the reason and moves to the next action.
7.  `PlanService` completes and returns the final `ExecutionReport`.
8.  The **CLI Adapter** formats and prints the report to the console.

## 5. Scope of Work (Developer Checklist)

### 1. Dependency Management
- [x] Add `pyperclip` to the `[tool.poetry.dependencies]` section in `packages/executor/pyproject.toml`.
    - *Note:* This dependency was installed and vetted via a technical spike during the architectural phase. It is already present in `pyproject.toml` and `poetry.lock`.

### 2. Port and Adapter Layer (`IUserInteractor`)
- [ ] **Port:** In the `IUserInteractor` interface, add the new method signature: `confirm_action(self, action_prompt: str) -> tuple[bool, str]`.
- [ ] **Adapter:** In `ConsoleInteractorAdapter`, implement the `confirm_action` method to handle the `y/n` and optional reason prompts as detailed in its design document.

### 3. Core Logic (`PlanService`)
- [ ] Modify the `PlanService.execute` method signature to accept the new `auto_approve: bool = False` parameter.
- [ ] Implement the interactive approval loop within the `execute` method. Before dispatching each action, check the `auto_approve` flag and call the `user_interactor` if necessary.
- [ ] If an action is skipped, create a `SKIPPED` `ActionResult` with the user's reason and append it to the report.

### 4. Inbound Adapter (`CLI`)
- [ ] Refactor `teddy_executor/main.py` to consolidate the CLI logic.
- [ ] Replace the existing top-level command with an `execute` subcommand using `typer.Typer()`.
- [ ] The `execute` function should accept an optional `plan_file: Optional[Path]` argument and a `--yes` flag.
- [ ] Implement the logic to read from the plan file if provided, otherwise read from the clipboard using `pyperclip.paste()`.
- [ ] Pass the plan content and the state of the `--yes` flag down to the `PlanService`.

### 5. Acceptance Testing
- [ ] Create a new test file: `packages/executor/tests/acceptance/test_interactive_execution.py`.
- [ ] Write a test case for the "happy path" of executing from the clipboard and approving all actions.
- [ ] Write a test case for skipping an action and verifying the reason is in the final report.
- [ ] Write a test case for executing from a file using the `--yes` flag to bypass all prompts.
- *Note:* You will need to mock `pyperclip` and the `ConsoleInteractorAdapter` to simulate user input in a non-interactive test environment.
