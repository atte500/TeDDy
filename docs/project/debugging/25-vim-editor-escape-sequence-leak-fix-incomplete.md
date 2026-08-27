# Bug: Vim Editor Terminal Escape Sequence Leak (Fix Incomplete)

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

When using vim to add a message during a session (pressing `e` to open editor), terminal escape sequences from the terminal emulator are captured as part of the user input after the editor closes. The user sees garbled text like `]10;rgb:8080/8989/b3b3` in the prompt response.

Bug #24 was marked "Resolved" but the symptom persists. The fix (`_flush_stdin()` in `ConsoleAskLoop`) flushes the stdin buffer immediately after launching the background editor — before the escape sequences are injected during editor runtime.

Expected: Clean user input without terminal control sequences.
Actual: OSC escape sequences from terminal emulator ↔ editor negotiation leak into the captured response.

## Context & Scope

### Regressing Delta
Commit `6e2381ef` (fix: enable TTY access for background editor and diff viewer launches) changed background subprocess stdin/stdout/stderr from `subprocess.DEVNULL` to `sys.stdin`/`sys.stdout`/`sys.stderr`. This is necessary for terminal editors to function, but it also allows terminal emulator OSC sequences to be written into the shared TTY input buffer during editor runtime.

### Environmental Triggers
- Terminal emulator that sends OSC escape sequences on editor launch (e.g., iTerm2, WezTerm, kitty when vim changes color palette).
- vim/neovim as the user's editor.
- The background editor flow in `ConsoleAskLoop` (console mode).

### Ruled Out
- The temp file content: `_read_editor_result()` reads the file directly, which never contains escape sequences. The leak is in the stdin read path.
- The old synchronous editor path (`_launch_editor_synchronous`) is not affected because it uses `run_command(cmd)` without `background=True`, so the parent waits for the editor and the stdin buffer is naturally flushed.

## Diagnostic Analysis

### Causal Model
The `ConsoleAskLoop.run()` loop:
1. User types 'e' → `_launch_editor_background()` spawns vim with TTY attached.
2. **Current fix:** `_flush_stdin()` is called immediately — before vim has started or the terminal emulator has written any response.
3. Loop continues with "Editor opened. Terminal reply or [Enter] to confirm editor › " prompt.
4. While vim runs, the terminal emulator writes OSC sequences (e.g., `]10;rgb:...`) into the TTY's stdin buffer as part of terminal-vim negotiation.
5. User finishes editing, closes vim.
6. User presses Enter → `_pt_prompt()` reads from stdin buffer → captures the buffered escape sequence + newline.
7. Since the captured text is non-empty, it is returned directly as the user's response.

The fix flushes too early (step 2), missing the sequences that arrive during steps 4-5.

### Discrepancies
- The regression test `test_console_ask_loop_stdin_flush.py` mocks `_launch_editor_background` and does not actually test the real timing scenario — it only verifies that `tcflush` is called after the mock call, not that it effectively clears sequences injected later.
- (resolved: spike confirmed)

### Investigation History
1. [Turn 4] Read Bug #24 case file — identified the early-flush flaw.
2. [Turn 4] Analyzed `_launch_editor_background` and `run()` loop — confirmed `_flush_stdin()` is called before editor actually runs.
3. [Turn 4] Created pty spike — pending execution.
4. [Turn 4] Identified correct fix location: flush must occur after the editor exits, i.e., in `_handle_empty_input` when `_active_editor_path` is set, before `_read_editor_result()`.

## Solution

### Root Cause
The `ConsoleAskLoop.run()` flow is:
1. User types `e` → `_launch_editor_background()` spawns vim with TTY attached (inherits `sys.stdin`/`sys.stdout`/`sys.stderr`).
2. **Current fix (Bug #24):** `_flush_stdin()` is called immediately — before vim has started or the terminal emulator has written any response.
3. Loop continues with "Editor opened. Terminal reply or [Enter] to confirm editor › " prompt.
4. While vim runs, the terminal emulator writes OSC sequences (e.g., `]10;rgb:...`) into the shared TTY input buffer as part of terminal-vim color negotiation.
5. User finishes editing, closes vim.
6. User presses Enter → `_pt_prompt()` reads from stdin buffer → `prompt_toolkit`'s `Vt100Parser` emits **every byte** of the OSC sequence as individual `KeyPress` events with `data` attribute → `prompt()` concatenates these into a single string and returns it as user input.
7. Since the captured text is non-empty, it is returned directly to `ask_question()`.

The `_flush_stdin()` call is too early (step 2) to catch sequences that arrive during steps 4-5. The root cause is that `prompt_toolkit` does **not** filter OSC escape sequences — they are treated as text input.

### The Fix
Add a `_strip_escape_sequences()` method to `ConsoleAskLoop` that uses a regex to remove all ANSI SGR and OSC escape sequences from text. This is applied to the user input returned by `_pt_prompt()` **when there is an active editor path**. This approach is:
- **Timing-independent:** Works regardless of when escape sequences arrive (before, during, or after editor runtime).
- **Non-destructive:** Only applied when `_active_editor_path` is set (i.e., after opening the editor). Normal text input is never filtered.
- **Belt-and-suspenders:** The existing `_flush_stdin()` is kept as a secondary defense; the stripping is the primary fix.

**Changes to `console_interactor_ask_loop.py`:**
1. Added module-level regex constant:
   ```python
   _ESCAPE_SEQUENCE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\][^\x1b]*(?:\x1b\\|\x07)")
   ```
   Matches ANSI SGR codes (`ESC[31m`) and OSC sequences (`ESC]...ST` where ST is `ESC\` or BEL `\x07`).

2. Added `_strip_escape_sequences(self, text: str) -> str` method that returns `_ESCAPE_SEQUENCE_RE.sub("", text)`.

3. In `run()`, after `user_input = self._pt_prompt(prompt_label).strip()`, added:
   ```python
   if self._active_editor_path:
       user_input = self._strip_escape_sequences(user_input)
   ```

### Preventative Measures
- **Audit all `background=True` subprocess calls:** Any background process with TTY attached that is followed by a user input read is vulnerable. The systemic audit confirmed only one such path exists (the editor flow). Future additions of background process calls must follow the same pattern.
- **Add to pre-commit review checklist:** Any `Popen` with `sys.stdin` as `stdin` that is followed by `input()` or `ptk_prompt` must be reviewed for escape sequence injection.
- **Consider upstream fix:** If `prompt_toolkit` ever adds native OSC filtering, the stripping function can be removed. Document this as `# TODO: Remove when ptk filters OSC natively`.

### Verification
- **Shadow file verification** (`spikes/debug/25-shadow-verify.py`):
  - 5 regex tests (OSC with ST, OSC with BEL, ANSI SGR, mixed, normal text) — ALL PASS.
  - 3 integration tests via shadow `ConsoleAskLoop` — ALL PASS.
  - Live `Vt100Parser` probe confirming OSC payload is captured as text and correctly stripped — PASS.
- **Regression test** (`test_console_ask_loop_escape_stripping.py`):
  - Mocks `_pt_prompt` to return OSC-containing string when `_active_editor_path` is set.
  - Asserts returned string is stripped of escape sequences.
  - Asserts normal text is unchanged.
- **Full test suite:** All unit and integration tests pass after applying the fix.
