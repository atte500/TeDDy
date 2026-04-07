# Experiment: Console Mode Input Regression

- **Related Artifacts:** [ConsoleInteractor](/src/teddy_executor/adapters/outbound/console_interactor.py), [ConsoleTooling](/src/teddy_executor/adapters/outbound/console_tooling.py)
- **Status:** Validating Assumption

## Objective & Requirements
Isolate the root cause of the terminal input corruption (`^M` appearing and blocked input) when running `teddy execute --console`.

### Requirements
- Restore the ability to provide `y/n/m` input immediately or correctly after preview.
- Ensure ENTER submits the input rather than printing carriage returns.
- Maintain compatibility with external diff/preview tools.

## Experiment Log

### Initial Context Gathering
- *Hypothesis:* The `ConsoleInteractor` uses a method to prompt for input that is sensitive to terminal mode changes caused by external pagers/editors.
- *Experiment:* READ the implementation of `ConsoleInteractor` and `ConsoleTooling`.
- *Observation:* `confirm_action` uses `typer.prompt` after `_handle_external_preview` runs `run_command`. `code` (VS Code) is configured with `--wait` which might be blocking.
- *Conclusion:* The interaction between subprocess-based tools and `typer.prompt` is the primary suspect.

### Baseline: Terminal State Corruption
- *Hypothesis:* Running a subprocess that interacts with the TTY before `typer.prompt` causes input blocking or `^M` corruption.
- *Experiment:* Create a spike that runs a blocking subprocess (`less`) and then prompts for input using `typer.prompt`.
- *Observation:* The spike timed out waiting for input, but the prompt was successfully reached. The user's `^M` observation confirms the terminal is in "raw" mode where newlines are transmitted as carriage returns that `input()` does not interpret as "End of Line".
- *Conclusion:* The TTY state is not being properly reset/cooked after external tool execution.

### Hypothesis: Manual TTY Sanitization
- *Hypothesis:* Explicitly calling `stty sane` or using `termios` to reset canonical mode after a foreground subprocess will fix the `^M` issue.
- *Experiment:* Implement a `_reset_terminal` method in a prototype interactor and call it after synchronous tool execution.
- *Observation:* Fix was integrated into `SystemEnvironmentAdapter`, but user reports it "still does not work". Latest screenshot shows a hang/missing output after the plan header.
- *Conclusion:* The fix is either insufficient or introduced a regression in output/blocking.

### Deep TTY State Investigation
- *Hypothesis:* `stty sane` might be blocking or insufficient. We may need to explicitly restore `echo` and `icanon`.
- *Experiment:* Investigate `echo_plan_summary` and the orchestration flow.
- *Observation:* Global `stty sane` in `SystemEnvironmentAdapter` appeared to cause a hang/output suppression. Reverting to targeted approach.
- *Conclusion:* Global reset is too broad.

### Targeted Diagnostic Iteration
- *Hypothesis:* The `^M` issue is likely due to the terminal remaining in non-canonical mode, but the fix must be applied specifically in the interaction loop to avoid side effects.
- *Experiment:* Revert global fix and provide a diagnostic spike.
- *Observation:* `stty sane` works in isolation. Hang occurs after "Reviewing Plan" title.
- *Conclusion:* Reverted global fix. Shifting to `termios` for direct, in-process terminal state management.

### Hypothesis: Non-Blocking Background Previews
- *Hypothesis:* Launching external previewers with `background=True` will prevent the CLI from waiting for the tool to close, resolving the "hang" behavior.
- *Experiment:* Update `ConsoleInteractorAdapter` to launch previews in the background.
- *Observation:* Previews now open immediately in the background without blocking the terminal prompt.
- *Conclusion:* Background execution is the correct model for external tools in console mode.

### Final Polish: Streamlined Skips
- *Hypothesis:* Removing the "Reason for skipping" prompt will improve the UX for rapid review.
- *Experiment:* Remove the prompt from `confirm_action`.
- *Observation:* User confirmed workflow is now smooth.
- *Conclusion:* UX streamlined for console mode.

## Analysis & Recommendations

### Gap Identification
1. **Production Reality:** The `ConsoleInteractorAdapter` currently launches external tools (diff viewers, editors) synchronously using `system_env.run_command`. It does not perform any terminal state restoration after these calls.
2. **Root Cause:** External TUI tools (like `less` or `code --wait` with a terminal fallback) often place the TTY in "raw" or "non-canonical" mode. If they crash or fail to restore the state perfectly, Python's `input()` (used by `typer.prompt`) fails to detect newlines, leading to the `^M` behavior.
3. **Integration Point:** While `ShellAdapter` could centralize the reset, it may be better placed in `ConsoleInteractor` to specifically protect the user's interactive loop, or inside a utility function.

### Delta Analysis Log
- *Investigation:* `git grep` revealed `system_env.run_command` is used in `ConsoleInteractorAdapter` and `textual_plan_reviewer_previews.py`.
- *Observation:* Both components launch external tools that can modify TTY state. `SystemEnvironmentAdapter` does not currently restore state.
- *Conclusion:* Centralizing the fix in `SystemEnvironmentAdapter.run_command` is the most robust approach to ensure all interactive tool handoffs are sanitized.

## Analysis & Recommendations

### Root Cause Analysis
1. **TTY State Corruption:** External tools (differs, editors, pagers) often put the terminal into "raw" mode. On macOS/Darwin, this frequently disables the `ICRNL` flag (Map Carriage Return to Newline) and `ICANON` (Canonical mode). This causes the ENTER key to send a carriage return (`^M`) that Python's `input()` does not recognize as a submission, leading to a perceived hang or corrupted input.
2. **Synchronous Blocking:** The `ConsoleInteractorAdapter` was launching external tools synchronously, forcing the CLI to wait for the window or process to close before surfacing the next prompt.

### Solution Design
1. **Multi-Layered Restoration:**
    - The `ConsoleInteractorAdapter` now forces `ICANON`, `ECHO`, and `ICRNL` flags active using the Python `termios` module immediately after tool execution and at the start of every prompt turn.
    - It uses `TCSAFLUSH` to purge the input buffer of any "ghost" carriage returns produced by the external tool.
    - The `SystemEnvironmentAdapter` provides a second line of defense by performing the same restoration in the `finally` block of `run_command`.
2. **Non-Blocking Previews:** External previewers are now launched in the background (`background=True`), unblocking the terminal prompt immediately.
3. **UX Streamlining:** Removed the optional "Reason for skipping" prompt to favor speed in console mode.

### Implementation Deliverables
- [src/teddy_executor/adapters/outbound/console_interactor.py](/src/teddy_executor/adapters/outbound/console_interactor.py): Implementation of `_restore_terminal` and background launches.
- [src/teddy_executor/adapters/outbound/system_environment_adapter.py](/src/teddy_executor/adapters/outbound/system_environment_adapter.py): Global terminal sanity check.

### Testability
Isolation was verified via `spikes/test_terminal_handoff.py` and `spikes/test_stty_diagnostics.py`. Final validation was performed manually by the user in a Darwin environment.
