# Bug: Mid-Plan Failure EXECUTE Returns Incorrect FAILURE

- **Status:** Resolved
- **Milestone:** [docs/project/milestones/02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md)
- **Vertical Slice:** [docs/project/slices/02-06-orchestrator-hardening.md](/docs/project/slices/02-06-orchestrator-hardening.md)
- **Specs:** [docs/project/specs/stability-and-bugfixes.md](/docs/project/specs/stability-and-bugfixes.md)

## Symptoms
The acceptance test `test_execute_mid_plan_failure_produces_report` is failing at the assertion `assert logs[0].status == "SUCCESS"`. The EXECUTE action (which writes to a file using `echo`) returns `FAILURE` when it should return `SUCCESS`. The captured log shows:
```
EXECUTE - Change content
FAILURE
```

## Context & Scope
### Regressing Delta
Three commits from Slice 02-06 introduced interactive prompt detection:
1. `8563b82b` - Added `_detect_interactive_prompt` static method and check in `_process_execution_results`.
2. `0335c11d` - Added `os.setsid()` preexec_fn and additional detection patterns ("read error", "Input/output error", "Inappropriate ioctl").
3. `3f84359c` - Swapped `subprocess.Popen` to `self._popen` for testability; added interactive detection in `_handle_timeout`; added Windows patterns ("Input required", "Unexpected EOF", "cannot read input").

The delta is in `ShellAdapter._prepare_subprocess_kwargs` (preexec_fn with os.setsid may change subprocess behavior) and `_detect_interactive_prompt` (may match false positives).

### Environmental Triggers
- Project directory path contains a space (`/Users/raphaelatteritano/Desktop/dev/TeDDy copy`) which may cause shell parsing issues when the workspace is a subdirectory with spaces.
- The test workspace path from `real_env.workspace` may contain spaces and be unquoted in shell commands.

### Ruled Out
[None yet]

## Diagnostic Analysis
### Causal Model
The EXECUTE command in the test `test_execute_mid_plan_failure_produces_report` uses an f-string with an unquoted file path: `f'echo "modified content" > {test_file}'`. When the project root contains a space in its path (e.g., `TeDDy copy`), the shell interprets the space as an argument delimiter. The redirection target becomes just the part before the space (`/Users/.../TeDDy`), which is a directory, producing the error `bash: ... TeDDy: Is a directory` and exit code 1. The ShellAdapter reports this as FAILURE.

The `_detect_interactive_prompt` logic in ShellAdapter is NOT involved — the failure is a genuine shell parsing error, not a false positive from pattern matching.

### Discrepancies
- The EXECUTE action "echo 'modified content' > test.txt" should succeed but returns FAILURE. The ShellAdapter's interactive prompt detection may be incorrectly classifying this command as interactive. (Resolved: The failure is a genuine shell parsing error — the file path contains a space and is unquoted. The MRE proved the shell error `"bash: ... TeDDy: Is a directory"` and exit code 1.)

### Investigation History
1. **Initial observation:** Test `test_execute_mid_plan_failure_produces_report` fails because EXECUTE action returns FAILURE instead of SUCCESS. Hypothesis: recent interactive prompt detection changes are misclassifying a simple echo command.
2. **Context gathering (Turn 1):** Read test file, ShellAdapter source, git log. Identified three commits introducing interactive detection. Created Case File. MRE was planned but not executed.
3. **MRE attempt (Turn 2):** Created MRE script that directly calls ShellAdapter with the same command. However, MRE failed due to `_validate_cwd` rejecting the /tmp workspace path. Need to fix MRE to use a project-relative path.
4. **MRE fix and confirmation (Turn 3):** Fixed MRE to use project-relative workspace. Output revealed the true error: `bash: line 4: /Users/.../TeDDy: Is a directory` with exit code 1. The shell splits the path at the space because the test command uses an unquoted f-string. This conclusively rules out the interactive detection hypothesis.
5. **Alignment (Turn 4-5):** Presented root cause to user. User confirmed and agreed to minimal fix (quote the path in the test). No systemic validation changes.

## Solution
[To be determined]
