# Test Plan: Comprehensive TUI Preview Verification
- **Status:** Green 🟢
- **Plan Type:** Implementation
- **Agent:** Pathfinder

## Rationale
````text
### 1. Synthesis
This plan is designed to stress-test the TextualPlanReviewer's ability to handle every supported action type in the TeDDy protocol.

### 2. Justification
By including all actions (CREATE, EDIT, EXECUTE, RESEARCH, READ, PRUNE, PROMPT, INVOKE, RETURN), we can verify that 'p' (Preview) and 'e' (Edit) behave correctly for each specific payload type.

### 3. Expected Outcome
The user should be able to navigate every action in the TUI, trigger non-blocking previews with 'p', and trigger non-blocking edits with 'e'.

### 4. State Dashboard
- Goal: Verify TUI interaction model.
- Status: Testing Phase.
````

## Action Plan

### `CREATE`
- **File Path:** [tests/test_file.txt](/tests/test_file.txt)
- **Description:** Test file for creation.
````text
This is a test file for the CREATE action.
It has multiple lines to test the editor view.
````

### `EDIT`
- **File Path:** [README.md](/README.md)
- **Description:** Test file for editing logic.

#### `FIND:`
````markdown
TeDDy's goal is to apply the **[UNIX philosophy](https://en.wikipedia.org/wiki/Unix_philosophy)**
````
#### `REPLACE:`
````markdown
TeDDy's goal is to apply the **UNIX philosophy** (small, sharp tools)
````

### `EXECUTE`
- **Description:** Test shell command execution.
- **Expected Outcome:** List of files is displayed.
````shell
ls -la
````

### `RESEARCH`
- **Description:** Test web search querying.
````text
textual tui keybindings
python anyio run_sync example
````

### `READ`
- **Resource:** [docs/architecture/ARCHITECTURE.md](/docs/architecture/ARCHITECTURE.md)
- **Description:** Test read-only context addition.

### `PRUNE`
- **Resource:** [docs/project/PROJECT.md](/docs/project/PROJECT.md)
- **Description:** Test context removal.

### `PROMPT`
This is a test of the PROMPT action. In the TUI, this should be selectable and potentially editable as a raw message.

### `INVOKE`
- **Agent:** Architect
- **Description:** Test agent handoff.
- **Reference Files:**
[docs/project/PROJECT.md](/docs/project/PROJECT.md)

### `RETURN`
- **Description:** Test task completion return.
- **Reference Files:**
[docs/architecture/ARCHITECTURE.md](/docs/architecture/ARCHITECTURE.md)
