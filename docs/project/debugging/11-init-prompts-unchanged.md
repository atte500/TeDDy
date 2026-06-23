# Bug: Init Reports "Prompts: unchanged." Despite Overwrites
- **Status:** Unresolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
**Expected behavior:** `teddy init prompts` should report "Prompts: overwritten (6 files)" or similar consistent message.
**Actual behavior:** The output says "Prompts: unchanged." on the first line, but then says "Prompts overwritten (6 files)." on the next line.
**Minimal reproduction steps:**
1. Run `teddy init prompts` when `.teddy/prompts/` already exists or doesn't exist.
2. Observe the output.

## Context & Scope
### Regressing Delta
The regressing delta is the addition of the `init` subcommand structure in `src/teddy_executor/__main__.py` (the `init_app` Typer with `prompts` and `config` subcommands). The `init_callback` was registered with `invoke_without_command=True` to handle `teddy init` alone, but it unconditionally calls `ensure_initialized(overwrite=False)` and prints the full summary even when a subcommand (e.g., `prompts`) is invoked. The subcommand then performs its own initialization with `overwrite=True` and prints a conflicting status. The bug was likely introduced when the subcommand structure was added without updating the callback to suppress its summary when a subcommand is active.

### Environmental Triggers
- The `.teddy/prompts/` directory must exist with all six XML files before running `teddy init prompts`.
- The bug manifests on any OS where TeDDy runs (confirmed on macOS; platform-independent).

### Ruled Out
- `InitService` logic is correct: both `ensure_initialized()` and `ensure_prompts_initialized()` work correctly in isolation.
- The conflict is not a file system issue; it's a CLI output ordering problem.
- The bug is not related to the `_ensure_project_initialized` helper or its adapter registration.

## Diagnostic Analysis
### Causal Model
The CLI defines an `init` typer with a callback (`init_callback`) registered with `invoke_without_command=True`:
1. When `teddy init prompts` is run, Typer first invokes `init_callback` because `invoke_without_command=True`.
2. `init_callback` calls `init_use_case.ensure_initialized(overwrite=False)` which checks existing prompts and returns the summary string `"Config: unchanged. Prompts: unchanged."`.
3. `init_callback` echoes the full line `"TeDDy initialized in .teddy folder. Config: unchanged. Prompts: unchanged."`.
4. Typer then dispatches to the `prompts` subcommand.
5. The subcommand calls `init_use_case.ensure_prompts_initialized(overwrite=True)`, which overwrites all six prompt files and echoes `"Prompts overwritten (6 files)."`.
6. The user sees both lines, creating confusion because the first line claims prompts are unchanged while the second line reports they were overwritten.

### Discrepancies
- `init_callback` reports "Prompts: unchanged." but immediately after the `prompts` subcommand overwrites them. **Conflict**: The status is misleading when a subcommand follows. **Resolved (via verification)**: Skipping the callback's summary when a subcommand is invoked eliminates the conflict.

### Investigation History
1. **Hypothesis**: The string "Prompts: unchanged." exists in production code. **Observation**: Only found in unit test; production code dynamically generates the string from `InitService._init_prompts()` when `count == 0`. **Conclusion**: The bug is a logical ordering issue, not a wrong string constant.
2. **Hypothesis**: Static analysis of `__main__.py` reveals `init_callback` calls `ensure_initialized(overwrite=False)` before the `prompts` subcommand calls `ensure_prompts_initialized(overwrite=True)`. **Observation**: Confirmed by reading source code; `init_callback` runs via `invoke_without_command=True`. **Conclusion**: The timing of callback vs. subcommand execution is the root cause.
3. **Hypothesis**: Running `teddy init prompts` locally will produce two conflicting lines. **Observation**: The command failed because `add_typer(init_app)` is called before `prompts` and `config` commands are defined on `init_app` (a separate ordering bug). **Conclusion**: Cannot reproduce via CLI locally; must use MRE with direct service calls.
4. **Hypothesis**: An MRE calling `ensure_initialized(overwrite=False)` then `ensure_prompts_initialized(overwrite=True)` will produce conflicting messages. **Observation**: MRE output: `TeDDy initialized in .teddy folder. Config: unchanged. Prompts: unchanged.` followed by `Prompts overwritten (6 files).`. Assertions passed. **Conclusion**: Empirically confirmed: the two-step service call reproduces the bug.

## Solution
### Root Cause
The `init_callback` in `src/teddy_executor/__main__.py` is registered with `invoke_without_command=True`. When a subcommand like `prompts` is invoked, Typer calls the callback first, which unconditionally runs `ensure_initialized(overwrite=False)` and prints a full summary including "Prompts: unchanged." (because prompts already exist). The subcommand then runs `ensure_prompts_initialized(overwrite=True)` and prints "Prompts overwritten (6 files).", creating contradictory output.

### Verified Fix
Modify `init_callback` to detect whether a subcommand will be invoked using Typer's `ctx.invoked_subcommand`. If a subcommand is active, skip the `ensure_initialized()` call and its `typer.echo(...)`, allowing the subcommand to handle its own output. The callback still runs `_ensure_project_initialized` and `prewarm_imports` for proper setup.

Zero-touch verification (`spikes/debug/11-fix-verification.py`) confirmed:
- **Scenario A** (`teddy init` alone, no subcommand): Full summary printed → PASS.
- **Scenario B** (`teddy init prompts`, with subcommand): Callback produces no output; only subcommand output printed → PASS.

### Preventative Measures
- **Pattern: Unconditional side effects in `invoke_without_command` callbacks.** To prevent this class of issue globally, enforce a coding standard: any callback registered with `invoke_without_command=True` that produces output must explicitly check `ctx.invoked_subcommand` before performing initialization or printing summaries. A pre-commit hook or lint rule could detect new `invoke_without_command=True` registrations and flag them for review.
- **Code review:** When adding subcommands under an existing `invoke_without_command` callback, review the callback to ensure it does not duplicate or conflict with subcommand logic.

### Implementation
1. Add `ctx: typer.Context` parameter to `init_callback`.
2. Check `ctx.invoked_subcommand` before calling `ensure_initialized()` and `typer.echo(...)`.
3. Write a regression test in `tests/suites/unit/` that simulates the callback+subcommand sequence and asserts no conflicting output.
4. Apply the change to `src/teddy_executor/__main__.py`.
5. Run the full test suite to confirm no regressions.
