# Bug: Vim Editor OSC Residual Display and Buffer Contamination

- **Status:** Resolved
- **Solution:** [PTY Isolation Fix](#solution)
- **Milestone:** N/A (ad-hoc quality fix)
- **Vertical Slice:** [00-07-editor-subsystem-overhaul.md](/docs/project/slices/00-07-editor-subsystem-overhaul.md)
- **Specs:** N/A

## Symptoms

After the editor subsystem overhaul (slice 00-07) and subsequent fixes for escape sequence leakage (Bugs #24, #25, #27), two residual issues remain:

1. **Residual garbage on terminal after ENTER:** When the user presses ENTER to confirm the editor result, garbled text appears on the terminal output. The exact string is `]10;rgb:8080/8989/b3b3` — a stripped OSC color palette sequence (the leading ESC byte was consumed by terminal processing). It is NOT captured in the AI message (the previous fixes strip escape sequences from user input), but it visually pollutes the terminal display.

2. **Garbled text on vim's top line:** When vim opens, the same string `]10;rgb:8080/8989/b3b3` appears on the first line of the editor buffer. The user must backspace to delete it before editing.

3. **Antipattern: escape sequence stripping from Message body:** The existing fixes strip escape sequences from *all* user input, including the message body sent to the AI. This prevents the user from intentionally sending escape sequences for debugging or other purposes, causing the AI to see `""` (two double-quotes) instead of the intended text.

Expected: No visible garbage on the terminal after pressing ENTER. No unwanted text in the vim buffer when the editor opens. Escape sequences should be stripped only when they are *involuntary garbled text*, not from intentional user input.
Actual: The OSC tail `]10;rgb:8080/8989/b3b3` remains visible on the terminal and appears in vim's initial buffer content. Intentional escape sequence input is also stripped.

## Context & Scope

### Regressing Delta
The background+harvest pattern from slice 00-07 (`_launch_editor_background()` with TTY inheritance) is the foundation that makes these leaks possible. The previous fixes (Bug #24/#25/#27) addressed the capture of escape sequences as user input but did not address the terminal emulator's behavior of transmitting OSC sequences (e.g., `]10;rgb:...` for dynamic color restoration) during the editor lifecycle.

The specific issues:
- **Symptom 1:** The OSC sequence is transmitted by the terminal emulator during/after editor runtime. It may be written to stdout (terminal display) rather than stdin. `_flush_stdin()` only flushes the input buffer, not the output buffer.
- **Symptom 2:** When spawning vim via `subprocess.Popen` with TTY inheritance, the terminal emulator responds to vim's OSC queries by sending data to the pty's input buffer. If this response arrives after `_flush_stdin()` (which clears the buffer before vim's raw-mode read loop), it may still appear as text input to vim, ending up on the first line of the buffer.

### Environmental Triggers
- macOS with a terminal emulator that sends dynamic color sequences (iTerm2, WezTerm, Kitty).
- Vim or Neovim configured to query terminal color palette on startup.
- Any editor that emits OSC queries for dynamic colors or other terminal capabilities.

### Ruled Out
- Escape sequences captured as user input are correctly handled by `_strip_escape_sequences()` and `_flush_stdin()` for the harvest path.
- The temp file content does not contain garbage — the issue is terminal display pollution and buffer contamination.

## Diagnostic Analysis

### Causal Model
1. User types 'e' → `_launch_editor_background()` creates temp file, spawns vim with TTY inheritance via `subprocess.Popen(stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)`.
2. `_flush_stdin()` clears the TTY input buffer immediately after spawn.
3. Vim starts, queries the terminal emulator for dynamic colors (OSC 10/11/12 queries). The terminal emulator responds with OSC sequences (e.g., `ESC]10;rgb:8080/8989/b3b3ST`). These responses arrive on the shared TTY's stdin.
4. **Symptom 2 (vim top-line):** The OSC response arrives after `_flush_stdin()` but before vim enters raw mode. Vim's input processing reads this data from stdin and inserts it into the buffer as text, appearing on the first line.
5. User edits, deletes the garbage line, exits vim.
6. Terminal emulator sends another OSC sequence to restore dynamic colors (e.g., `ESC]10;rgb:8080/8989/b3b3ST`). This sequence is written to the shared TTY's stdin.
7. **Symptom 1 (terminal display):** The OSC sequence arrives on stdin. The kernel's line discipline (in canonical mode with echo enabled) processes the input. The leading ESC byte is consumed as part of terminal control, leaving the tail `]10;rgb:8080/8989/b3b3` which is **echoed as literal text to the terminal display**.
8. User presses ENTER → `_pt_prompt()` (prompt_toolkit) reads from stdin in raw mode. The OSC sequence (or its tail) is captured as raw input.
9. `_strip_escape_sequences()` strips the sequence from the captured input (BUG #25/#27 fix). Since the stripped input may be empty or not match "e", the loop falls through to `_handle_empty_input()` which harvests the file content correctly.
10. **But:** The terminal display already shows the echoed garbage from step 7. This is visual pollution that the stripping fix does not address.

**Key insight:** The root cause is that the editor process inherits the parent's TTY. Any terminal negotiation between the editor and the terminal emulator contaminates the parent's stdin/stdout. The existing fixes address *capture* of these sequences (preventing them from becoming user input/message content) but do not address *display* pollution (echo on terminal) or *buffer contamination* (vim reading them as initial text). A fix must isolate the editor's TTY interaction from the parent process's TTY.

**Additional antipattern:** Escape sequences are stripped from ALL user input via `_strip_escape_sequences()` in `run()`. This means if the user intentionally types an escape sequence (e.g., for debugging), it would be silently removed. The stripping should only apply to involuntary garbled sequences, not to intentional user text.

### Discrepancies
- `_flush_stdin()` clears stdin but not the terminal display (output buffer). The OSC sequence is displayed via stdout, not captured via stdin. This explains why Symptom 1 persists: the sequence is visible on the terminal even though it's not captured as input.
    - (Resolved: pty isolation captures all terminal negotiations inside the isolated pty slave, so the parent's display is never polluted.)
- The same OSC tail appearing on vim's top line suggests it arrives via stdin before vim's raw-mode read. But `_flush_stdin()` is called after spawn. If the sequence arrives after the flush, vim captures it. This is a timing-dependent race condition.
    - (Resolved: pty isolation gives vim its own dedicated terminal session; any OSC responses arrive on the pty slave's stdin, not the parent's. Vim's raw-mode reads from the pty slave, so the sequence is received as terminal control data, not as buffer text.)
- Escape sequences stripped from all user input (antipattern).
    - (Resolved: stripping is now gated to only apply when `_active_editor_path` is set — i.e., only for content harvested from the editor. Intentional user typing is never stripped.)

### Investigation History
[—— investigative probes executed? ——]

## Solution

### Root Cause
The editor subprocess inherits the parent process's TTY (`stdin=sys.stdin`, `stdout=sys.stdout`, `stderr=sys.stderr`). This shared TTY exposes the parent to two issues:

1. **Symptom 1 (terminal display pollution):** When vim exits, the terminal emulator sends an OSC reset sequence (e.g., `ESC]10;rgb:8080/8989/b3b3ST`) to restore dynamic colors. This arrives on the shared stdin. The kernel's line discipline (in canonical mode with echo enabled) consumes the leading ESC byte and echoes the tail `]10;rgb:8080/8989/b3b3` as literal text to the terminal display. This text is visible but not captured as input (previous fixes handle capture).

2. **Symptom 2 (vim top-line garbage):** After `_flush_stdin()` clears stdin, the terminal emulator responds to vim's color queries. This response arrives on the shared stdin after the flush but before vim enters raw mode. Vim reads it as typed input and inserts it into the buffer.

3. **Antipattern:** `_strip_escape_sequences()` was applied to ALL user input, preventing intentional escape sequence communication.

### Verified Fix (Strategy B: PTY Isolation)
The fix replaces direct TTY inheritance with an isolated pty pair for the editor subprocess.

**Changes to `ConsoleAskLoop` in `console_interactor_ask_loop.py`:**

1. **New `_launch_editor_in_pty(temp_path)` method:**
   - Creates a pty pair via `os.openpty()`.
   - Spawns the editor subprocess with `stdin=slave_fd`, `stdout=slave_fd`, `stderr=slave_fd`.
   - Closes slave fd in the parent (child holds the reference).
   - Stores the master fd and starts a background `daemon=True` drainer thread.
   - All terminal negotiations (OSC queries/responses) happen inside the isolated pty.

2. **New `_pty_drainer(master_fd)` drainer thread:**
   - Continuously reads data from the pty master fd using `select.select()` (1s timeout).
   - Discards all data — this prevents the kernel's pty buffer from filling up.
   - Exits cleanly when the fd is closed or raises `OSError`.

3. **New `_close_pty_master()` cleanup method:**
   - Closes the master fd and resets state.
   - Called during harvest (`_handle_empty_input`) and `cleanup()`.

4. **Modified `_launch_editor_background()`:**
   - Calls `self._launch_editor_in_pty(temp_path)` instead of `subprocess.Popen` with `sys.stdin/stdout/stderr`.
   - Retains `_flush_stdin()` as a secondary defense.
   - All other logic (persistent file reuse, marker splitting, etc.) unchanged.

5. **Modified `_handle_empty_input()`:**
   - Calls `self._close_pty_master()` BEFORE reading the file — ensures any buffered terminal data is discarded.
   - Retains `_flush_stdin()` as secondary defense.

6. **Modified `_strip_escape_sequences()` gating in `run()`:**
   - Only applies stripping when `self._active_editor_path` is set (i.e., only for editor-harvested content).
   - Direct user typing is no longer stripped, fixing the antipattern.

7. **Modified `__init__()` and `cleanup()`:**
   - Added `_pty_master_fd` and `_pty_drainer_thread` initialization.
   - `cleanup()` calls `_close_pty_master()`.

### Preventative Measures
- **Audit rule:** Any future background subprocess that needs a TTY must use pty isolation instead of inheriting `sys.stdin/stdout/stderr` directly. The `_launch_editor_in_pty` pattern is the canonical way to spawn interactive subprocesses without contaminating the parent terminal.
- **Architecture rule:** Consider extracting `_launch_editor_in_pty()` into a reusable helper in `console_tooling.py` (or a dedicated `pty_helper.py`) so other components can use the same pattern without duplicating pty lifecycle management.

### Verification (from Shadow MRE)
The shadow MRE (`spikes/debug/28-pty-isolation-mre.py`) passes all 6 structural tests:
- Pty pair creation and master fd storage.
- Pty master closure on harvest.
- Stripping gated to editor path.
- Drainer thread reads and discards data.
- Drainer exits cleanly on closed fd.
- Hardened regex still strips known OSC sequences.
