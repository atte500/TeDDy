# Bug: History log contains ANSI escape codes

- **Status:** Resolved
- **Milestone:** [N/A](/docs/project/milestones/02-stability-and-polish.md) (likely part of Milestone 2: Stability & Infrastructure)
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

**Expected:** The `history.log` file in session directories should contain plain text log entries, readable as-is via `cat` or any log viewer.

**Actual:** The log contains ANSI escape codes (e.g., `\x1b[33m`, `\x1b[0m`) which cause garbled output when viewed in a terminal, and pollute log processing tools.

**Reproduction Steps:**

1. Run a TeDDy session (e.g., `teddy start ...`).
2. Open the generated `history.log` in the session directory.
3. Observe raw ANSI escape sequences interspersed with log text.

## Context & Scope

### Regressing Delta

The bug is not a regression from a specific change; the `_TeeWriter.write()` method in `src/teddy_executor/core/utils/io.py` has never stripped ANSI escape codes. The delta is the absence of an ANSI cleaning step. Commit `[unknown]` introduced the Tee, but no code was ever added to filter escape sequences from the log file.

### Environmental Triggers

No special environment required – any OS that emits ANSI codes to stdout/stderr will reproduce the issue. In TeDDy sessions, the CLI formatter (`cli_formatter.py`) emits colored output (e.g., yellow warnings, green success messages), which is captured by the Tee.

### Ruled Out

- The formatter itself (ANSI codes are correct for terminal display).
- The logging module (handlers are properly replaced in `Tee.__enter__`).
- Session‑specific logic (the Tee is the single point of transcription).

## Diagnostic Analysis

### Causal Model

1. During a turn, the orchestrator or lifecycle manager installs a `Tee` (wrapping `sys.stdout` and `sys.stderr` with `_TeeWriter`).
2. All output (print, logging, formatter) flows through `_TeeWriter.write()`.
3. `write()` copies the *exact same bytes* to both the terminal and the history.log file.
4. Because the output contains ANSI escape sequences (colored terminal text), those sequences end up verbatim in the log.
5. Nothing downstream strips or cleans the log content before it is read or displayed.

**Root cause:** `_TeeWriter.write()` does not strip ANSI escape codes before writing to the log file. The fix is to apply a regex substitution within that method for the log‑only branch. **Fix verified via shadow file `spikes/debug/shadow_io.py` (MRE exit 0).**

### Discrepancies

- None observed. The MRE clearly confirms the causal model.

### Investigation History

1. **Hypothesis:** ANSI codes originate from the Tee’s pass‑through behavior. **Observation:** Reading `io.py` – `_TeeWriter.write()` copies text verbatim, no stripping. **Conclusion:** Confirmed – Tee is the direct cause.
2. **Hypothesis:** ANSI codes can be reproduced with a minimal script. **Observation:** MRE (24‑history‑log‑ansi‑codes‑mre.py) exits 0 and confirms `\x1b[...` sequences in log. **Conclusion:** Bug is reproducible and causal model validated.
3. **Hypothesis:** Adding ANSI stripping regex in `_TeeWriter.write()` will clean the log without affecting terminal output. **Observation:** Shadow file `spikes/debug/shadow_io.py` with regex substitution tested via MRE – log contains only plain text. **Conclusion:** Fix verified empirically without touching production code.

## Solution

**Root cause:** `_TeeWriter.write()` in `src/teddy_executor/core/utils/io.py` copies the exact same bytes to both the terminal and the history.log file without stripping ANSI escape sequences. Because the CLI formatter emits colored output (e.g., `\x1b[33m`), those sequences end up verbatim in the log.

**Fix (verified via shadow file):** Add an ANSI escape regex substitution to `_TeeWriter.write()` before writing to the log file. The terminal stream retains raw text (colours preserved), while the log branch applies `re.compile(r"\x1b\[[0-9;]*[a-zA-Z]").sub("", text)`.

**Preventative measure:** Establish a design rule that any output-capturing component (`Tee`-like utility) MUST strip terminal escape sequences from the archival/disk target. A centralized `strip_ansi()` helper should be provided in the `core/utils` module to avoid regex duplication. Also, consider adding a lint rule or an automated check (e.g., see "cargo cult" pattern) to flag any future logging/tee implementations that write raw stream output without sanitization.

### Systemic Audit

**Root Cause Category:** Unfiltered write-through in output-capture utilities. The `_TeeWriter` class writes input bytes verbatim to both the live stream and the archival file. This pattern is dangerous when archival output is later read by plain-text tools; any terminal escape sequences become pollution.

**Categorical Audit Results:**
- The codebase contains only one `Tee`-like class: `_TeeWriter` / `Tee` in `src/teddy_executor/core/utils/io.py`. No other utility performs raw stdout/stderr capture to disk.
- No other `Capture` or `Redirect` classes were found in `src/`.
- The `history.log` file is written exclusively by the `Tee` class (guarded creation in `session_orchestrator.py` and `session_lifecycle_manager.py`). No other code writes to `history.log`.

**Impact Audit:**
- The fix modifies only the `_TeeWriter.write()` method — the single point where text flows to disk.
- Consumers of the `Tee` class (two call sites: `session_orchestrator.py` and `session_lifecycle_manager.py`) pass a `Path` and rely on the `with` context; they are unaffected by the internal implementation change.
- No shared contracts, DTOs, or Ports are altered.
- The fix is fully localised and has zero external impact.
