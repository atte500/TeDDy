# Bug: Windows Editor-Open Stutter
- **Status:** Resolved
- **Milestone:** [Milestone 4: TUI & UX Enhancements](/docs/project/milestones/04-tui-ux-enhancements.md)
- **Vertical Slice:** None yet
- **Specs:** None

## Symptoms
- **Expected:** Pressing the editor key opens the configured external editor without a perceptible pause. The same action is instantaneous on macOS.
- **Actual:** On Windows 11 the editor open shows a visible stutter.
- **Reproduction:** Start an interactive session on Windows, review a plan in the TUI, press the editor key, and observe the pause before the editor responds.

## Context & Scope
### Regressing Delta
Commits `14abbbab` (add Windows platform branching) and `8e10164e` (differentiate CLI vs GUI editors on Windows) introduced the Windows no-suspend synchronous branch. Commit `8e10164e` added `_run_editor_process`, a synchronous `subprocess.run` with `CREATE_NO_WINDOW`, and routed the annotated diff path through it on Windows, which blocks the Textual event loop until the editor launcher returns. The classification lookups it depends on are keyed on extension-less names: `ConsoleToolingHelper._DIFF_FLAGS` in `console_tooling.py`, and `_CLI_EDITORS` in both `textual_plan_reviewer_editor.py` and `console_interactor_ask_loop.py`. The Windows `.CMD` launcher suffix defeats every one of them.

### Environmental Triggers
- OS: Windows 11 with the `cmd.exe` shell.
- Editor: `codium` (VSCodium, a GUI editor). `where codium` resolves `C:\Users\rapha\AppData\Local\Programs\VSCodium\bin\codium.cmd`.
- Terminal: not a factor. Probe 04 ran without a TTY and still blocked for about 1228ms, so the freeze is independent of the terminal.

### Ruled Out
- Editor resolution cost: `which('codium')` and `find_editor()` both take about 2ms, so the PATH scan is not the stutter.
- `get_diff_viewer_command()` cost: about 2ms.
- Temp-file staging (`create + write + chmod`): about 0.6ms.
- `Popen` return latency for a `.cmd` launcher: 2-9ms, so returning control is not the stutter.
- Synchronous wait duration is the blocker, not the spawn. Probe 04 measured the real `codium.CMD` at 1228ms cold and 1218ms warm, while a background spawn returns in about 9ms.

## Diagnostic Analysis
### Causal Model
Windows resolves the configured GUI editor to `codium.CMD`. The editor routing compares `os.path.basename(...)` (or its lowercase form) against tables keyed on extension-less names: `ConsoleToolingHelper._DIFF_FLAGS`, `_CLI_EDITORS`, and the vim set. The `.CMD` suffix therefore misses every lookup. Two consequences follow. First, `get_diff_viewer_command()` finds no `_DIFF_FLAGS` entry and returns the bare editor path with no `--diff` flag. Second, `_uses_annotated_diff_path()` classifies codium as an unknown editor and routes EDIT previews into the annotated single-file diff flow. On Windows that flow calls `_run_editor_process()`, a synchronous `subprocess.run` with `CREATE_NO_WINDOW`, and never enters `app.suspend()`, so the Textual event loop blocks until the launcher chain returns. Probe 02 measured a 1045ms block against an 8ms background `Popen` return. Probe 04 measured the real `codium.CMD` launcher at 1228ms cold and 1218ms warm, which matches the user-perceived stutter. macOS resolves a bare `codium`, matches `_DIFF_FLAGS`, and uses the non-blocking background `run_command(background=True)` diff path.

The same mismatch misclassifies CLI editors on Windows. A `codium.CMD`-style wrapper for a terminal editor such as `nvim.CMD` is absent from `_CLI_EDITORS`, so `launch_editor` would treat a terminal editor as a GUI editor and show the ConfirmScreen while the editor still occupies the terminal.

After the basename normalization, a residual risk remains. An editor wrapper that is absent from `_DIFF_FLAGS` still routes into the annotated flow, and that flow blocks the event loop on Windows. Every known GUI editor lives in `_DIFF_FLAGS`, so the residual affects only unregistered wrappers. The recommended follow-up launches the annotated diff file through the background plus ConfirmScreen pattern for non-CLI editors on Windows.

### Discrepancies
- [x] The editor-open path pauses on Windows while the same path is instantaneous on macOS (Resolved: Windows `.cmd` suffix breaks extension-less basename lookups, misrouting codium into the synchronous annotated diff path).
- [x] `get_diff_viewer_command()` returns `['...codium.CMD']` with no `--diff` flag on Windows (Resolved: `_DIFF_FLAGS` is keyed on `codium`, not `codium.cmd`).
- [x] The annotated diff path blocks the Textual event loop on Windows (Resolved: probe 02 measured a 1045ms synchronous block versus an 8ms background spawn).
- [x] A Windows CLI editor wrapper is misclassified as a GUI editor (Resolved by the same mechanism: `_CLI_EDITORS` and the vim set are keyed on extension-less names).
- [x] The real `codium.CMD` blocks the TUI for a perceptible interval (Resolved: probe 04 measured a 1228ms cold and a 1218ms warm synchronous wait).

### Investigation History
1. Read the editor launch chain in `textual_plan_reviewer_editor.py`, `console_tooling.py`, and `core/utils/terminal.py` to identify the platform-specific branches.
2. Read the local config and PATH resolution; observed `editor: codium` resolving to `codium.cmd`, so the GUI branch is the exercised Windows path.
3. Ran [probe 01](/spikes/debug/windows-editor-open-stutter/01-editor-open-latency-mre.py); observed every pre-spawn stage and the `Popen` return in the low single-digit milliseconds, which ruled out resolution, staging, and spawn-return as the stutter. The same probe showed `get_diff_viewer_command()` returning `['...codium.CMD']` with no `--diff` flag, which exposed the `.cmd` basename-mismatch misrouting.
4. Ran [probe 02](/spikes/debug/windows-editor-open-stutter/02-diff-routing-and-blocking-mre.py); observed `uses_annotated_diff=True` for the real `codium.CMD` command and `False` for the extension-stripped `codium`, with `_DIFF_FLAGS` returning `['--diff']` only for the stripped name. A simulated one-second GUI launcher blocked `_run_editor_process` for 1045ms while a background `Popen` returned in 8ms, which proves the annotated path is the stutter mechanism.
5. Ran the sandbox replica built by [build_replica.py](/spikes/debug/windows-editor-open-stutter/build_replica.py) and proven by [03-normalize-basename-mre.py](/spikes/debug/windows-editor-open-stutter/03-normalize-basename-mre.py); observed `_uses_annotated_diff_path([codium.CMD]) = False`, `_is_cli_editor([nvim.CMD]) = True`, `_is_vim_editor([nvim.CMD]) = True`, and a 9.51ms background launch, which proves the shared basename normalization repairs the routing.
6. Ran [probe 04](/spikes/debug/windows-editor-open-stutter/04-real-launcher-duration-mre.py); observed the real `codium.CMD` launcher return after 1228ms cold and 1218ms warm, which confirms that the synchronous annotated path blocks the event loop for the perceived stutter duration.

## Solution
### Root Cause
Windows resolves the configured editor through `shutil.which`, which returns the launcher wrapper `codium.CMD`. Three classification functions compare the extension-less `os.path.basename` against tables keyed on bare names, so the `.CMD` suffix defeats every lookup. `get_diff_viewer_command()` therefore returns `['...codium.CMD']` without the `--diff` flag, and `_uses_annotated_diff_path()` classifies codium as an unknown editor. The unknown-editor route selects the annotated single-file diff flow, which on Windows calls `_run_editor_process()` synchronously with `CREATE_NO_WINDOW` and outside `app.suspend()`. The Textual event loop therefore blocks for the whole launcher duration, measured at 1228ms cold and 1218ms warm for the real `codium.CMD`.

Commit `8e10164e` introduced the regression when it added `_run_editor_process` and routed the annotated diff path through it on Windows. Commit `14abbbab` added the surrounding platform branching.

The fix normalizes the editor basename in one shared helper before every lookup. The helper strips the Windows launcher suffixes `.cmd`, `.bat`, and `.exe` and lowercases the remainder. The proof is preserved in the sandbox. [build_replica.py](/spikes/debug/windows-editor-open-stutter/build_replica.py) stages [replica_textual_plan_reviewer_editor.py](/spikes/debug/windows-editor-open-stutter/replica_textual_plan_reviewer_editor.py) with the normalization applied, and [03-normalize-basename-mre.py](/spikes/debug/windows-editor-open-stutter/03-normalize-basename-mre.py) prints GREEN: `_uses_annotated_diff_path([codium.CMD])` returns False, `_is_cli_editor([nvim.CMD])` and `_is_vim_editor([nvim.CMD])` return True, and the background diff launch returns in 9.51ms.

The fix is proven in the sandbox replica and NOT applied to `src/`. It touches three production modules and four test modules, which exceeds the direct-fix scope, so it requires a Developer handoff.

### Affected Components
- `src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py`: call the shared normalization in `_is_cli_editor`, `_uses_annotated_diff_path`, and `_is_vim_editor`. Consumers are `launch_editor` (lines 333 and 338) and `preview_edit_diff_viewer` (lines 408, 442, and 452).
- `src/teddy_executor/adapters/outbound/console_tooling.py`: call the shared normalization in `get_diff_viewer_command` before the `_DIFF_FLAGS` lookup at line 145.
- `src/teddy_executor/adapters/outbound/console_interactor_ask_loop.py`: remove the duplicated `_CLI_EDITORS` set and the `_is_cli_editor` static method at lines 43 and 67, then delegate to the shared helper. The `_launch_editor_background` consumer at line 222 stays unchanged.
- Shared helper placement: the helper must live in a module that both adapter layers can import without a cycle, so `core/utils/` is the correct home (for example `core/utils/editor_names.py`). `console_tooling.py` must not import from the inbound adapter.
- `tests/suites/unit/adapters/inbound/test_tui_editor_suspend_resume.py`: extend the `_is_cli_editor`, `_is_vim_editor`, and annotated-routing cases with `.CMD`, `.BAT`, and `.EXE` variants.
- `tests/suites/unit/adapters/outbound/test_cli_editor_classification.py`: extend the ask-loop classification cases with launcher-suffix variants.
- `tests/suites/unit/adapters/outbound/test_console_tooling_editor.py`: add a `get_diff_viewer_command()` case proving `codium.CMD` now returns the `--diff` flag.
- `tests/suites/unit/adapters/outbound/test_console_ask_loop_wiring.py`: keep the import surface green after the ask-loop delegation.
- Follow-up outside this fix: route non-CLI editors through the background plus ConfirmScreen pattern in `preview_edit_diff_viewer` on Windows, so unregistered wrappers cannot block the event loop.
