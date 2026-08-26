# Bug: TUI Editor Invocation and Message Input Silent Failure
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
- **Expected:** When pressing 'e' in the TUI plan reviewer, the configured editor (e.g., vim) opens for editing the plan. When pressing 'm', a message input prompt appears for the user to add a message.
- **Actual:** Pressing 'e' shows the prompt "Editor opened. Terminal reply or [Enter] to confirm editor ›" but no editor actually opens — the user is stuck. Pressing 'm' does nothing (no visible reaction).
- **Minimal Reproduction Steps:**
  1. Configure `editor: "vim"` in `.teddy/config.yaml`.
  2. Run `teddy start`.
  3. After the plan is generated, press 'e' to edit the plan.
  4. Observe "Editor opened. Terminal reply or [Enter] to confirm editor ›" appears.
  5. Press Enter — nothing happens, no editor window opens.
  6. Press 'm' — no response observed.

## Context & Scope
### Regressing Delta
The editor invocation failure is **not a regression** from a recent commit — it is a design-level defect in the background editor launch mechanism present since the initial implementation. Both `ConsoleAskLoop._launch_editor_background()` (console mode) and `spawn_editor()` (TUI mode) use `subprocess.Popen` with `stdin=subprocess.DEVNULL`, `stdout=subprocess.DEVNULL`, `stderr=subprocess.DEVNULL`, and `start_new_session=True`. This prevents terminal-based editors (vim, nvim, nano) from attaching to the TTY, causing them to fail silently.

The 'm' key issue in console mode is also a design-level defect: `ConsoleAskLoop.run()` only handles `'e'` as a special command; any other character (including `'m'`) is treated as a plain response string and passed no further.

### Environmental Triggers
- **Symptom 1 ('e' editor prompt):** Occurs in **console mode** (not TUI). The "Editor opened. Terminal reply or [Enter] to confirm editor ›" prompt originates from `console_interactor_ask_loop.py:48`.
- **Symptom 2 ('m' does nothing):** Occurs in both console mode (no handler, character passed as response) and TUI mode (editor spawns invisibly, but `ConfirmScreen` modal appears).
- macOS (Darwin 25.5.0) — all Unix-like systems affected.
- Editor configured as `vim` or any terminal-based editor (nvim, nano, vi).

### Ruled Out
- TUI-specific rendering issues (the code paths for 'e' and 'm' in TUI exist and are correctly wired, `action_add_message` returns `add_message_logic` which calls `add_message_handler` which calls `launch_editor`).
- Dependency/import failures (TextualPlanReviewer imports resolve correctly; no silent fallback from TUI to console mode exists in `reviewer.py`).
- Key binding registration (bindings for 'e' → `edit_details` and 'm' → `add_message` are present in `BINDINGS` and both have corresponding `action_*` methods).
- TTY detection (the console ask loop's `_is_tty()` correctly detects stdin TTY, but the editor is disassociated via `DEVNULL` regardless).

### Systemic Audit Findings
**Category:** Terminal-interactive subprocess spawned with DEVNULL streams (TTY detachment)

**All Popen+DEVNULL occurrences across `src/`:**

| # | File | Lines | Context | Needs Fix? |
|---|------|-------|---------|------------|
| 1 | `system_environment_adapter.py` | 19-27 | `run_command(background=True)` — launches editor/diff viewer | YES — needs TTY for vim/nvim/nano |
| 2 | `textual_plan_reviewer_editor.py` | 38-44 | `spawn_editor()` — launches editor | YES — same issue |
| 3 | `textual_plan_reviewer_editor.py` | 142-148 | `preview_edit_diff_viewer()` — launches diff viewer (vimdiff/etc.) | YES — diff tools also need TTY |

**All subprocess.run with DEVNULL occurrences:**
- `system_environment_adapter.py:54` — `run_command(background=False)` — synchronous run with `stdin=DEVNULL` only. Safe: synchronous execution captures output via pipe, does not need TTY.
- `shell_adapter.py:86` — `execute()` — `subprocess.run(stdin=DEVNULL, ...)`. Safe: executes batch commands, STDOUT/STDERR captured via `capture_output=True`. Separate code path from editor launching.

**Consumers of `run_command(background=True)` (will be impacted by fix):**
- `console_interactor.py:136` — launches editor for interactive diff preview
- `console_interactor.py:138` — launches diff viewer
- `console_interactor_ask_loop.py:107` — launches editor for user response
Total: 3 production call sites, all editor/diff — no EXECUTE impact.

**Consumers of `spawn_editor()` (will be impacted by fix):**
- `textual_plan_reviewer_editor.py:110` — called from `launch_editor()` — 1 production call site (plus definition at line 28).

**Consumers of `launch_editor()` (upstream chain):**
- `textual_plan_reviewer_previews.py` — 7 call sites: lines 70, 97, 119, 183, 209, 225, plus `preview_edit_diff_viewer()` at line 156.
- `console_interactor_ask_loop.py` — 2 call sites: lines 54, 78.
- `console_interactor.py` — 2 call sites: lines 54, 181.

**Impact assessment:**
- The fix (inherit std streams instead of DEVNULL for background subprocesses) affects only editor/diff viewer launching.
- EXECUTE actions (`ShellAdapter.execute()`) use a completely separate code path (`subprocess.run` with `capture_output=True`) and are NOT impacted.
- The 3 production call sites of `run_command(background=True)` all pass editor/diff commands built via `find_editor()` / `find_diff_tool()` from `ConsoleTooling`.
- The `preview_edit_diff_viewer()` direct Popen call in `editor.py` also passes diff viewer commands — same TTY requirement.
- No batch/headless processes are spawned with background=True, so the fix is safe across all consumers.

**Regression risk:** None identified. The only consumers are terminal-based editor/diff launching which explicitly need TTY.

## Diagnostic Analysis

### Causal Model

**Symptom 1: Pressing 'e' shows "Editor opened. Terminal reply or [Enter] to confirm editor ›" but the editor never appears.**

The user is in **console mode** (not TUI). The flow is:
1. `ConsoleAskLoop.run()` loop shows `"Response (type 'e' for editor) › "` prompt.
2. User presses 'e' → `_launch_editor_background()` is called.
3. `_launch_editor_background()` creates a temp file with the prompt and a `<!-- Please enter your response above this line. -->` marker, then calls `self._tooling.find_editor()` to resolve the editor command.
4. If editor is found (e.g., vim), it calls `self._system_env.run_command(cmd, background=True)`.
5. `SystemEnvironmentAdapter.run_command()` with `background=True` calls:
   ```python
   subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
   ```
6. Terminal-based editors (vim, nvim) **require a TTY** to display their UI. By binding all three std streams to `/dev/null` and setting `start_new_session=True`, the editor process is orphaned from the terminal and either:
   - Exits immediately with an error (detecting no TTY)
   - Or runs "headless" (e.g., vim in non-interactive batch mode) with no visible window
7. The user sees `"Editor opened. Terminal reply or [Enter] to confirm editor ›"` but the editor is invisible or dead. Pressing Enter then triggers `_handle_empty_input()` → `_read_editor_result()`, which reads the temp file (still containing only the marker) and returns an empty string, or may crash if the editor process left the file locked.

**Symptom 2: Pressing 'm' does nothing.**

- **In console mode:** `ConsoleAskLoop.run()` does not handle 'm'. The loop treats any non-'e' non-empty input as a response and returns it immediately. The character 'm' is silently returned as the user's answer to the prompt.
- **In TUI mode:** `action_add_message()` → `add_message_logic()` → `add_message_handler()` is correctly invoked. `add_message_handler()` calls `await launch_editor(app, current_message, suffix=".md")`. Inside `launch_editor()`, if `TEDDY_TEST_MOCK_EDITOR_OUTPUT` is not set (production), it creates a temp file and calls `spawn_editor(editor_cmd, temp_file)`. `spawn_editor()` uses the same `subprocess.Popen` with `DEVNULL` streams (see `textual_plan_reviewer_editor.py:38-44`). The editor spawns invisibly (same TTY issue). However, `launch_editor()` then calls `await _confirm_and_harvest()` which pushes a `ConfirmScreen` modal with text *"Do you want to apply the changes? (y/n)"*. This modal **does** appear in the TUI, but:
  - The user expects a message input prompt, not a "changes" confirmation.
  - If the user presses 'y', `_confirm_and_harvest` tries to read the temp file (which may still contain only the initial marker, or be empty if the editor never touched it), returning the unmodified content.
  - The user perceives this as "nothing happened" because the editor window never appeared.

**Root cause (both symptoms):** Background editor spawning without TTY attachment — `subprocess.Popen` with `stdin=subprocess.DEVNULL`, `stdout=subprocess.DEVNULL`, `stderr=subprocess.DEVNULL` — prevents terminal-based editors from being visible to the user.

### Discrepancies
- The user reports "pressing 'm' does nothing" in TUI. However, the code shows that `ConfirmScreen` should appear. **Resolved:** The modal *does* appear but is not recognized by the user as a message input — it says "Do you want to apply the changes? (y/n)" which is confusing in the message context.
- The user reports pressing 'e' shows the console prompt "Editor opened...". This confirms they are in **console mode**, not TUI mode, for that symptom. **Resolved:** The editor process is actually launched but invisible due to `DEVNULL` streams, confirmed by the MRE probe (vim PID 3053 stayed alive 2+ seconds with no visible window).
- The user reports both symptoms occurring in the same session. The first symptom (editor prompt) is necessarily console mode, while the second ('m' does nothing) could be either mode. **Resolved:** In console mode, 'm' is treated as a response. In TUI mode, 'm' triggers the correct handler but the editor is invisible. The two symptoms share the same root cause (background editor without TTY) but manifest differently depending on mode.
- No existing regression test covers background editor launch with a terminal-based editor. **Noted for Systemic Audit.**

### Investigation History
1. **Traced key bindings and imports:** Confirmed 'e' → `action_edit_details()` → `edit_action_logic()` → `handle_edit_action()` → `launch_editor()` + `spawn_editor()`. Confirmed 'm' → `action_add_message()` → `add_message_logic()` → `add_message_handler()` → `launch_editor()`. Established both code paths are correctly wired. [Turn 1-2]
2. **Traced "Editor opened" prompt origin:** Found at `console_interactor_ask_loop.py:48`. Confirmed this is **console mode**, not TUI. The user is in console mode for the 'e' symptom. [Turn 2]
3. **Traced `run_command(background=True)`:** Found `SystemEnvironmentAdapter.run_command()` (line 19-27) calls `subprocess.Popen` with `stdin=subprocess.DEVNULL`, `stdout=subprocess.DEVNULL`, `stderr=subprocess.DEVNULL`, `start_new_session=True`. Hypothesized this prevents TTY attachment. [Turn 4]
4. **Created MRE probe (`spikes/debug/23-editor-launch-test.py`):** Simulated exact `subprocess.Popen` call with `/usr/bin/vim`. Result: vim PID 3053 stayed alive 2+ seconds but produced **no visible window**. **Root cause verified: terminal-based editors cannot display when spawned with all streams bound to DEVNULL.** [Turn 7]
5. **Analyzed reviewer registry (`reviewer.py`):** Confirmed no silent TUI→console fallback exists. Mode is chosen strictly by `ui_mode` config or `--tui/--console` flag. [Turn 7]
6. **Confirmed console mode 'm' behavior:** `ConsoleAskLoop.run()` only checks for `'e'` as special command. All other characters (including 'm') are returned as the response string. [Turn 2]
7. **Zero-Touch Verification (Shadow File):** Created `spikes/debug/shadow_system_environment_adapter.py` with the fix (inherit parent std streams instead of DEVNULL). Ran MRE which confirmed: BROKEN behavior (DEVNULL) → vim stays alive but invisible, FIXED behavior (inherit TTY) → vim launches without crash, can parse TTY output. **Zero-Touch Verification PASSED.**
   - [Turn 20-21]

## Solution

### Root Cause
Both `ConsoleAskLoop._launch_editor_background()` (console mode) and `spawn_editor()` (TUI mode) use `subprocess.Popen` with `stdin=subprocess.DEVNULL`, `stdout=subprocess.DEVNULL`, `stderr=subprocess.DEVNULL`, and in one case `start_new_session=True`. Terminal-based editors (vim, nvim, nano) require a TTY to display their UI. By disconnecting all three standard streams from the parent terminal, the editor process cannot attach to the TTY and either runs invisibly or exits immediately with "Vim: Warning: Input/Output is not to a terminal".

A third occurrence exists in `preview_edit_diff_viewer()` at `textual_plan_reviewer_editor.py:142-148`, which directly spawns a diff viewer (e.g., `nvim -d`) with the same DEVNULL pattern.

### The Fix
Change `subprocess.Popen` calls in background editor/diff launching to inherit the parent process's standard streams:

**File 1: `system_environment_adapter.py` — `run_command(background=True)`**
```python
# Before:
subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                 stderr=subprocess.DEVNULL, start_new_session=True)
# After:
subprocess.Popen(args, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
```

**File 2: `textual_plan_reviewer_editor.py` — `spawn_editor()`**
```python
# Before:
subprocess.Popen(cmd + [str(path)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                 stderr=subprocess.DEVNULL)
# After:
subprocess.Popen(cmd + [str(path)], stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
```

**File 3: `textual_plan_reviewer_editor.py` — `preview_edit_diff_viewer()`**
```python
# Before:
subprocess.Popen(diff_viewer + [str(before), str(p_file)], stdin=subprocess.DEVNULL,
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
# After:
subprocess.Popen(diff_viewer + [str(before), str(p_file)], stdin=sys.stdin, stdout=sys.stdout,
                 stderr=sys.stderr)
```

**Note:** In TUI mode, the Textual `app.suspend()` context manager (used in `launch_editor()` before calling `spawn_editor()`) already handles terminal handover/restore, allowing the editor to use the terminal. In console mode, inheriting streams directly is sufficient since the parent process already owns the TTY.

### Preventative Measures
1. **Code review rule:** Any `subprocess.Popen` call with `DEVNULL` streams must be reviewed to confirm it is NOT a terminal-interactive tool. Editor/diff viewer spawns must always inherit parent TTY.
2. **Grep pattern:** Add to pre-commit or CI: check for Popen + DEVNULL where the command is a known editor/diff tool (vim, nvim, nano, diff, etc.).
3. **Architecture rule:** Background subprocess spawning for user-facing interactive tools should go through a single, well-tested method (e.g., `ISystemEnvironment.run_command(background=True)`) rather than raw `Popen` calls scattered across the codebase. The `preview_edit_diff_viewer()` function should ideally also use `run_command(background=True)` instead of direct Popen.
