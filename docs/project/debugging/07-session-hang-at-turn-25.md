# Bug: Session hangs at turn 25 and cannot be interrupted (q / Ctrl+C)
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** [docs/project/slices/00-37-prompt-xml-to-md-migration.md](/docs/project/slices/00-37-prompt-xml-to-md-migration.md)
- **Specs:** N/A

## Symptoms
Expected: An interactive session runs turn-by-turn, and the user can interrupt the in-flight turn with `q` or `Ctrl+C` at any time; `teddy resume` continues an existing session.
Actual: Session `20261015_174430-implement-vertical-slice-prompt-xml` stalls at turn 25 (turn 25 has `input.md`, `meta.yaml`, and `turn.context` but no `plan.md` and no `report.md`; `history.log` ends at "[25] … Waiting for Developer to respond…"). `teddy resume` stalls at the same point, and neither `q` nor `Ctrl+C` exits.

Minimal reproduction: [spikes/debug/session-hang/05-backtick-strip-mre.py](/spikes/debug/session-hang/05-backtick-strip-mre.py) deterministically reconstructs the degenerate plan (a single ~252,310-backtick run) and proves the sanitization fix (see Solution): the REAL unbounded path produces a 757,043 B section while the sanitized replica collapses it to 116 B (6,526×). The interrupt mechanism was proven sound during investigation — a raising SIGINT handler unwinds `select.poll`, `select.select`/kqueue, `socket.recv`, asyncio `sock_recv`, and a real `litellm.completion`, and a direct `kill -INT` exits the live hung processes (see Investigation History items 9–11).

## Context & Scope
### Regressing Delta
Not a code regression. The defect is a long-standing missing size cap on embedded session-history content in `ContextService._format_session_history` (`src/teddy_executor/core/services/context_service.py`), exposed by a one-shot LLM degeneration in turn 24. The uncommitted Deliverable 2a (`.md`-priority prompt resolution) was ruled out as unrelated.

### Environmental Triggers
macOS (Darwin 25.5.0), interactive terminal, session rooted at `.teddy/sessions/20261015_174430-implement-vertical-slice-prompt-xml/`.

### Ruled Out
- Turn-25 plan validity: no plan.md exists, so the stall precedes plan persistence.
- Deliverable 2a resolvers contain no unbounded loop (static inspection of the diff).
- Prompt resolution (`.md`-priority): `.teddy/prompts/` and the session root hold only `.xml`, so `prefer_markdown` is a behavioural no-op for this session.
- A Python-level infinite loop: the live process's main thread is parked in `select_poll_poll` (a network wait), not a CPU loop.
- The interrupt MECHANISM: a raising SIGINT handler unwinds `select.poll`, `select.select`/kqueue, `socket.recv`, asyncio `sock_recv`, AND a real `litellm.completion` (~0.5–1.1 s). A direct `kill -INT` exits the live hung processes. The mechanism is sound.
- A "stale installed build": the installed `teddy-cli` 0.1.17.dev1285 ships the quit-key listener, the ISIG-restoring `restore_cooked_mode`, and `InterruptGuard` (with `enter_waiting`).
- `restore_terminal_mode` (console_interactor_helpers.py): it delegates to `core.utils.terminal.restore_cooked_mode`, which re-enables `ISIG | IEXTEN`.
- The `except KeyboardInterrupt` control flow: the session-loop boundary prints the interrupt reason, stops the listener, restores the handler, and exits cleanly (it does not loop or retry).

## Diagnostic Analysis
### Causal Model
Turn 24's `plan.md` contains a single 252,310-character all-backtick line (a one-shot LLM repetition degeneration; per-turn backtick totals are flat ~50–250 for turns 01–23 then jump to 252,434). `ContextService._format_session_history` embeds that plan verbatim into turn 25's Session History, and `get_fence_for_content` (core/utils/markdown.py) sizes the wrapping fence to `max_backtick_run + 1` = 252,311 at BOTH ends. Reproduced by running the real helper over the real file: `plan_bytes 257517` → `fence_len 252311`. Turn 25's `input.md` therefore balloons to 1,101,931 B (~5× the prior turn), and the planning step (hydration/token-count/LLM call) blocks on that oversized payload; the live process's main thread is parked in `select_poll_poll`. The interrupt failure (q / Ctrl+C) is not yet explained: `InterruptGuard._handle_signal` raises `KeyboardInterrupt` whenever `_executing` is False, and planning runs with `_executing=False`, so the interrupt SHOULD unwind. The failure is therefore SIGNAL DELIVERY, not mechanism: the two `start` TTYs were `-isig` (a real Ctrl+C generates no signal), while the `resume` TTY kept `isig`. The quit-key listener's `_enter_noncanonical_mode` clears only `ICANON | ECHO` and KEEPS ISIG, preserving whatever state it inherits; prompt_toolkit's vt100 raw mode clears ISIG while active and restores it on clean exit, making the ask loop the prime source of an inherited `-isig`. A direct `kill -INT` exits the live hung processes, confirming delivery is the only gap.

### Discrepancies
- [x] Session stalls at turn-25 planning while turn 24 reported SUCCESS. → RESOLVED: turn 24 succeeded because its plan was persisted; the stall is turn 25's PLANNING, which re-embeds the degenerate turn-24 plan and blocks on the oversized payload.
- [x] `q` and `Ctrl+C` do not interrupt the stall. → RESOLVED: the interrupt path is sound (raising handler unwinds all blocking primitives + real litellm; direct `kill -INT` exits). The failure is delivery — `-isig` on the `start` TTYs kills Ctrl+C. `q` self-delivers SIGINT via the listener (independent of ISIG) and should work; residual ambiguity noted below (processes were killed before re-probing).
- [x] `teddy resume` stalls at the same point. → RESOLVED: resume re-assembles the same oversized session-history context and blocks identically.
- [x] A raising SIGINT handler should interrupt a blocking `select.poll()`, yet the live stall is not interruptible. → RESOLVED: the handler DOES interrupt every blocking primitive; the live stall was not interruptible because no SIGINT was actually DELIVERED (terminal `-isig`), not because the handler failed.

### Investigation History
1. Inspected the session directory tree and `history.log`; observed turn 25 has `input.md`/`meta.yaml`/`turn.context` but no `plan.md`/`report.md`, and turn 24 logged SUCCESS — the stall precedes plan persistence.
2. Inspected the uncommitted Deliverable-2a diff; observed three resolver rewrites routed through `prefer_markdown`, none containing an unbounded loop.
3. Confirmed prompt resolution is NOT the hang (`.teddy/prompts/` holds only `.xml`); located the "Waiting for ..." banner at planning_service.py:40 (first line of generate_plan).
4. Located a live hung process (PID 27593, `teddy resume`); native `sample` shows the main thread in `select_poll_poll` (network wait), ruling out a Python-level infinite loop.
5. Quantified the context explosion: turn 24 plan.md = 257,546 B with a single 252,310-char all-backtick line; turn 25 input.md = 1,101,931 B.
6. Measured the growth curve: per-turn plan backtick totals flat (~50–250) for turns 01–23, exploding to 252,434 at turn 24 — a one-shot LLM degeneration, not cross-turn escalation.
7. Proved the fence amplification by running `get_fence_for_content` over the real turn-24 plan: `plan_bytes 257517` → `fence_len 252311`, matching the measured turn-25 section sizes (257,177 B and 504,989 B).
8. Read the interrupt wiring: `_orchestrate_session_loop` installs `InterruptGuard`, starts the quit listener, and wraps the loop in `except KeyboardInterrupt`; `enter_executing` is called only at action dispatch, so planning runs with `_executing=False`.
9. Proved the interrupt MECHANISM sound: a raising handler unwinds `select.poll`, `select.select`/kqueue, `socket.recv`, and asyncio `sock_recv` (~0.5 s each).
10. Proved a real `litellm.completion` against a never-responding local server IS interrupted by the raising handler (~1.1 s), ruling out litellm swallowing SIGINT.
11. Proved a direct `kill -INT` EXITS the live hung processes (27593, 29064) immediately — delivery, not mechanism, is the exit defect.
12. Measured terminal modes: the two `start` TTYs (ttys007/ttys009) were `-icanon -isig` (Ctrl+C dead); the `resume` TTY (ttys005) and the debugger TTY kept `isig`. The listener clears only `ICANON | ECHO` and keeps ISIG, preserving the inherited state.
13. Confirmed the session-loop control flow: the `except KeyboardInterrupt` block prints the interrupt reason, stops the listener, restores the handler, and exits cleanly (no loop/retry). `enter_waiting` is never called.
14. Refuted the `restore_terminal_mode` hypothesis: it delegates to `restore_cooked_mode`, which re-enables `ISIG | IEXTEN`. prompt_toolkit's vt100 raw mode (`input/vt100.py:268`) clears ISIG while active and restores it on clean exit (`:307`).
15. Sandbox-verified the fix: a capped replica of `_format_session_history` collapses the real turn-24 section from 762,186 B to 139,672 B (5.5×) without touching `src/`.
16. Systemic audit: `get_fence_for_content` is called from `_format_session_history` and `_format_workspace_contents`; the workspace path reads via `read_files_in_vault`, which BYPASSES `read.max_lines`, so both embed sites share the amplification category. Both `start` (session_cli_handlers.py:622) and `resume` (:1125) route through `_orchestrate_session_loop`. The installed build (0.1.17.dev1285) ships all interrupt fixes.
17. Refined the fix per user direction (sanitize, not cap): sandbox-verified a backtick-run sanitizer, collapsing a deterministically reconstructed ~252,310-backtick run — REAL unbounded section 757,043 B → SANITIZED 122 B (6,205×) — without truncating legitimate content. Audited the guardrails: `turn_context_threshold` is consumed only by `session_pruning_service` (item-level, excludes session.context), and `PlanningService.generate_plan` computes `token_count` and `get_context_window` only for DISPLAY (no over-budget comparison/raise).
18. Addressed the user's nested-fence concern: raised the collapse threshold from a naive 3 to a generous 20 (collapse to 3) and extended the MRE with an explicit assertion that a genuine 4-backtick nested fence survives byte-for-byte — PASS alongside the 6,205× collapse. Per the user's "just sanitize" preference, folded the proposed plan-rejection guardrail into the sanitizer as a log rather than a new validation rule.
19. Replaced the arbitrary threshold with the user's proposed semantic detector (per user: "check if there is trailing opening codeblock instead of checking for threshold"): `strip_trailing_open_fence` walks the fence structure and removes a dangling opening fence. Sandbox-verified on the reconstructed degenerate plan — REAL unbounded section 757,043 B → SANITIZED 116 B (6,526×) — while a genuine 4-backtick nested fence AND a normal balanced code block are both preserved byte-for-byte.
20. Proved the detector's reliability against a case matrix ([spikes/debug/session-hang/06-fence-detector-matrix.py](/spikes/debug/session-hang/06-fence-detector-matrix.py)): 10 well-formed shapes (balanced backtick/tilde, nested 4-wraps-3, mixed blocks, inline code mid-line/own-line, indented code, no fences, prose after block, block at EOF) are ALL preserved byte-for-byte, while 4 unclosed cases (giant backtick run, giant tilde run, unclosed opener with content — both chars) are ALL collapsed ("ALL PRESERVE+COLLAPSE PASS"). Three already-malformed shapes (mismatched fence lengths, odd fence count, a block whose body is a giant backtick run) are MUTATED per CommonMark fence semantics; documented, not asserted. Confirms the detector recognises BOTH fence characters and never flags a genuine (balanced) code block.

## Solution
### Root Cause
Unbounded verbatim embedding of externally-influenced content (a session-history file) into the assembled context payload, amplified by `get_fence_for_content` sizing the fence to the longest backtick run in that content. One degenerate plan line (252k backticks) inflated turn 25's payload ~5× (1,101,931 B).

### Verified Fix (sandbox-proven) — strip the trailing unclosed fence
Detect and remove a code fence that is OPENED but never CLOSED in embedded content BEFORE computing the fence, at the shared embed seam. Well-formed Markdown has balanced fences; an LLM degeneration that emits a giant run of backticks (the observed turn-24 plan had a single ~252,310-backtick run) leaves an unclosed opening fence. Stripping that dangling fence removes the pathological run — and therefore the fence amplification `get_fence_for_content` derives from it — with NO magic number and without touching legitimate (balanced) code blocks. Proven in [spikes/debug/session-hang/05-backtick-strip-mre.py](/spikes/debug/session-hang/05-backtick-strip-mre.py): the REAL unbounded section is 757,043 B, the SANITIZED replica is 116 B (6,526×), against a deterministically reconstructed degenerate plan, while a genuine 4-backtick nested fence AND a normal balanced code block are both preserved byte-for-byte. The detector is structural — it acts ONLY when the content ends inside an open code block — and it recognises BOTH fence characters (backticks AND tildes). A 10-case reliability matrix ([spikes/debug/session-hang/06-fence-detector-matrix.py](/spikes/debug/session-hang/06-fence-detector-matrix.py)) confirms every well-formed shape (balanced backtick/tilde, nested 4-wraps-3, mixed blocks, inline code, indented code) is preserved byte-for-byte while unclosed backtick AND tilde runs are collapsed. (Nuance: only backticks cause fence amplification — `get_fence_for_content` counts backticks only — but the detector also strips unclosed tilde runs to remove the raw content bloat.)

```python
# In core/utils/markdown.py — a single seam used by both embed sites:
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")

def strip_trailing_open_fence(content: str) -> str:
    """Remove a trailing, UNCLOSED opening code fence from ``content``.

    Walks the fence structure: if the content ends INSIDE an open code block,
    that dangling opening fence line is removed. Balanced content — including a
    legitimate nested fence — is returned byte-for-byte unchanged.
    """
    lines = content.split("\n")
    open_char: str | None = None
    open_len = 0
    open_index: int | None = None
    for index, line in enumerate(lines):
        match = _FENCE_RE.match(line)
        if match is None:
            continue
        fence, info = match.group(1), match.group(2)
        if open_char is None:
            open_char, open_len, open_index = fence[0], len(fence), index
        elif fence[0] == open_char and len(fence) >= open_len and not info.strip():
            open_char, open_len, open_index = None, 0, None
    if open_index is None:
        return content
    del lines[open_index]
    return "\n".join(lines)
```
Apply it to `content_str` in `ContextService._format_session_history` and to `content` in `_format_workspace_contents`, BEFORE calling `get_fence_for_content(...)`. Because the fence is derived from the (now-sanitized) content, it can no longer be amplified; the MRE pins both the collapse and the byte-for-byte preservation of legitimate fences.

### Systemic Fix
Add a single shared helper `embed_in_fence(content, lang)` in `core/utils/markdown.py` that sanitizes then fences, and route BOTH `_format_session_history` and `_format_workspace_contents` through it, closing the "unbounded/amplified embed" category at one seam. Note `read_files_in_vault` intentionally bypasses `read.max_lines`, so the guard must live at the embed site, not the read site.

### Preventative Measures
1. **Bound the content, not the fence (defence in depth):** `get_fence_for_content` derives the fence FROM the content, so clamping the fence alone is ineffective (it would break the Markdown without shrinking the payload). The content is what must be bounded; the trailing-open-fence strip is the primary bound. (Residual: a theoretical BALANCED giant run evades unclosed-fence detection; address it with a high-bound content sanity check only if such a case ever appears.)
2. **Fail gracefully on an over-budget request (Jidoka):** `PlanningService.generate_plan` already computes `token_count` and `get_context_window(model)`, but only to DISPLAY them — it never compares the two. Add a pre-call check that raises a clear, user-visible error when `token_count` exceeds the window (or a safety margin), turning a silent stall into a visible failure. This is a guardrail, NOT the hang's confirmed cause: the observed stall was a stalled oversized request (~1.1 MB, plausibly within the ~1M-token window), not a returned "context length exceeded" error.
3. **Surface a degeneration via the sanitizer, not a new rule (per user: "just sanitize"):** instead of a plan-rejection validation rule, have `strip_trailing_open_fence` log when it strips a fence, so an LLM degeneration still leaves a visible Jidoka trace without blocking the turn.
4. **Close the Ctrl+C delivery gap:** ensure any component that clears ISIG (prompt_toolkit raw mode, the TUI reviewer) restores it on exit, and/or have the quit-key listener re-enable ISIG in `_enter_noncanonical_mode` rather than preserving an inherited cleared state.

### Residual: the `q` path
`q` self-delivers SIGINT via the listener and is independent of terminal ISIG; static analysis says it should work, and turn 6 observed the listener thread alive and polling. The live processes were killed in turn 9 (as a diagnostic), so this could not be re-probed end-to-end. Best hypothesis: the user's Ctrl+C was dead (`-isig`) and the `q` impression may have been a re-hang on the immediately following `resume`, or a transient stdin-ownership window. Not blocking; the primary hang fix removes the stall that made the exit path matter.
