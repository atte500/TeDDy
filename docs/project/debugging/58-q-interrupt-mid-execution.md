# Bug: q-interrupt-mid-execution

- **Status:** Resolved
- **Milestone:** [N/A]
- **Vertical Slice:** [N/A]
- **Specs:** [docs/project/specs/interactive-session-workflow.md](/docs/project/specs/interactive-session-workflow.md)

## Symptoms

Expected: Pressing `q` during plan execution should *gracefully* interrupt the plan — abort the action currently in flight, skip the remaining actions of the plan, and still finalize the turn by generating `report.md` (the turn must remain auditable).

Actual: Pressing `q` during execution is silently ignored. Furthermore, once `q` has been pressed (and ignored) during execution, pressing `q` in *subsequent* turns (where quitting is expected to work, e.g. the interactive prompt/reviewer loop) no longer quits. The quit mechanism appears to be permanently disabled for the remainder of the session.

Minimal reproduction:
1. Start an interactive session (`teddy start`).
2. Queue a plan whose execution takes non-trivial time (e.g. a long `EXECUTE`).
3. Press `q` while the plan is executing.
4. Observe: execution continues to completion; no interrupt.
5. In the next interactive prompt, press `q` to quit.
6. Observe: `q` is ignored — the session does not quit.

## Context & Scope

### Regressing Delta
The quit-key interrupt feature is under construction in slice `00-21-session-interrupt-resume-message`. The workspace was fast-forwarded (Turn 9) from `0c4c64ea` to `f51e9ff2`; the relevant delta is commit `9b7b3e3e` ("start and stop the quit-key listener around the turn loop"), which ADDED the session-loop wiring — `session_cli_handlers.py` now resolves `IQuitKeyListener`, calls `quit_listener.start()` ONCE before the turn loop and `quit_listener.stop()` in the boundary `finally` (`:303-304`, `:358`). The listener itself (commits `538c62b0`/`d741b41a`) is a process-global singleton whose reader thread is one-shot.

### Environmental Triggers
TTY-only (the listener is a no-op when `sys.stdin.isatty()` is False); a long in-flight `EXECUTE` (the window where the interrupt is meaningful); the process-global singleton lifetime shared across turns; POSIX non-canonical terminal mode.

### Ruled Out
- `ExecutionOrchestrator._process_plan_actions`: the drain machinery is fully implemented (`enter_executing()` + `guard.interrupted.is_set()` skip loop) and still assembles `report.md`.
- `InterruptGuard`: the WAITING/EXECUTING phase state machine is implemented and unit-tested; boundary/ports guard identity is asserted by `test_session_loop_interrupt_wiring.py`.
- The pre-pull hypothesis "the session-loop boundary never `start()`s the listener": FALSIFIED — the wiring exists at HEAD (`9b7b3e3e`).

## Diagnostic Analysis

### Causal Model
Verified from code (post fast-forward to `f51e9ff2`):
- `_orchestrate_session_loop` (`session_cli_handlers.py`) resolves the process-global `IQuitKeyListener` singleton and calls `quit_listener.start()` ONCE, before the `while True:` turn loop; `quit_listener.stop()` runs in the boundary `finally` at session end (`:303-304`, `:358`). The `InterruptGuard` handler is installed once for the whole loop.
- `TerminalQuitKeyListener.start()` sets non-canonical TTY mode (ICANON|ECHO off, ISIG kept) and spawns ONE daemon reader thread. `_read_loop` polls one byte at a time; `_process_byte()` returns `True` on the quit key (`0x71`) ⇒ the `_read_loop` `break`s ⇒ the reader thread EXITS PERMANENTLY after the first `q`. `_trigger()` self-delivers `os.kill(os.getpid(), SIGINT)` (no `on_quit` injected in production).
- `InterruptGuard`: in WAITING (`_executing=False`) SIGINT raises `KeyboardInterrupt`; in EXECUTING (`_executing=True`, entered by `ExecutionOrchestrator._process_plan_actions`) the first SIGINT sets `interrupted`, and the per-action loop skips remaining actions with `INTERRUPT_REASON` while still assembling the report.

Root cause (symptom #2) — HIGH CONFIDENCE: the listener is started ONCE per SESSION while its reader thread is ONE-SHOT. After the first `q` press the thread is dead for the rest of the session, so no later `q` (in subsequent turns' wait windows) is ever observed. This exactly reproduces "after pressing `q` once, subsequent `q` to quit no longer works".

Symptom #1 (`q` during execution is "ignored") — mechanism RESOLVED (post fast-forward + Turn-10 reads/grep):
- The session execution path DOES enter EXECUTING: `SessionOrchestrator.execute()` → `ExecutionOrchestrator.execute()` → `_process_plan_actions()`, whose `ExitStack` wraps the whole per-action loop in `enter_executing()` (candidate (a) discarded).
- In EXECUTING a `q`/SIGINT sets `interrupted`, but the drain is only consulted at the TOP of the per-action loop (`if guard.interrupted.is_set(): skip`). The IN-FLIGHT action is never interrupted — it runs to completion. `ShellAdapter` launches each `EXECUTE` in its OWN session (`preexec_fn` → `os.setsid()`), so the reader's `os.kill(os.getpid(), SIGINT)` reaches only the parent and the child keeps running (candidate (b) CONFIRMED; (c)/(d) discarded).
- Consequence: when the long action is the last (or only) action of the plan — the user's cited repro — the flag is set but there is nothing left to skip, so the turn completes with NO observable change ⇒ `q` appears "ignored".
- Asymmetry: `enter_waiting()` is NEVER called in production (grep: only its definition at `interrupt_guard.py:91`); `_executing` is False everywhere except inside `_process_plan_actions`, so a `q` during planning/review takes the WAITING branch (raises `KeyboardInterrupt` → session exits).

Net causal conclusion: BOTH symptoms share ONE enabling defect — the reader thread is ONE-SHOT while it is `start()`ed ONCE per session:
  • #1 "ignored" = the in-flight action is not interrupted (the drain skips only subsequent actions) AND the first `q` already kills the reader;
  • #2 "no longer works" = the reader thread is dead for the rest of the session, so no later `q` is ever observed.

Zero-Touch Verification result: the MRE (`spikes/debug/58-q-interrupt-mid-execution-mre.py`) drives the REAL `_read_loop` with three queued `q` bytes. Against production it reports `trigger count: 1 (expected 3)` (one-shot); against the shadow replica with a PERSISTENT read loop (`spikes/debug/shadow_terminal_quit_key_listener.py`) it reports `trigger count: 3 (expected 3)`. This empirically isolates the one-shot reader as the defect and proves a persistent read loop resolves it, with `src/` untouched.

Resolved at Alignment (user-selected Option B, explicitly superseding the Task-Brief 00-21 "let the in-flight action finish" semantics): a bare `q` must TERMINATE the in-flight action (kill its isolated process group), log it `ActionStatus.INTERRUPTED`, skip the remaining actions as `SKIPPED`, and still generate `report.md` with `RunStatus.INTERRUPTED`. The user also requires that a bare `q` while WAITING for input (initial request / awaiting reply) must NOT quit — the reader backs off while `stdin_owned()` is claimed. This is handed to the Developer via [Slice 00-23](/docs/project/slices/00-23-quit-key-in-flight-interrupt.md).

### Discrepancies
- Pre-pull hypothesis "the listener is never started" contradicted the container comment. (resolved: the local checkout was 5 commits behind `origin/main`; the wiring landed in `9b7b3e3e` — the listener IS started once per session at the turn-loop boundary.)
- The listener is `start()`ed once per SESSION but its reader thread is ONE-SHOT (dies on the first `q`). Contradicts the implied intent that one long-lived listener serves every turn's wait window. (resolved: confirmed as the core defect behind symptom #2 — the reader's `_read_loop` `break`s on `_process_byte() == True`, and `test_quit_listener_lifecycle_wraps_the_turn_loop` pins start-once-per-session.)
- Symptom #1 (first `q` during execution "ignored") had no confirmed mechanism. (resolved: SIGINT IS delivered and sets `interrupted`, but the drain skips only actions AFTER the in-flight one — which is never interrupted (it runs in its own session). For a last/only long action there is nothing to skip ⇒ no observable effect; worsened by the reader dying on that same first `q`.)

### Investigation History
1. Case File created from session request.
2. Read port/adapter/guard/orchestrator + session-loop boundary. Finding: `InterruptGuard` is installed at the boundary, but `IQuitKeyListener` is never resolved/started there. (superseded — see 5.)
3. Full-tree census of quit-key references: only port + adapter + `container.py` registration exist in `src/`; no production `start()`/`stop()` call site. TUI grep found a single `q` binding (`textual_plan_reviewer_app.py:73` → `cancel`). (superseded — see 5.)
4. Discovered the local branch was 5 commits behind `origin/main` (git status). Read-only `git grep origin/main` proved the wiring exists remotely: `session_cli_handlers.py:303` resolves `IQuitKeyListener`, `:304` `start()`, `:358` `stop()` (commit `9b7b3e3e`).
5. Fast-forwarded the workspace to `f51e9ff2` and read the live boundary, adapter, guard and orchestrator. Confirmed: listener started ONCE per session (`:303-304`), stopped in `finally` (`:358`); `TerminalQuitKeyListener._process_byte()` returns True on the first `q` ⇒ reader thread exits permanently; `_trigger()` self-delivers SIGINT. → start-once + one-shot = symptom #2 root cause (high confidence).
6. Read the live `session_orchestrator.py`, `shell_adapter.py`, reader unit tests, and ran a phase/signal census. Confirmed: the session path reaches `_process_plan_actions` (EXECUTING); `ShellAdapter` uses `preexec_fn`→`os.setsid()` so the in-flight `EXECUTE` child is NOT killed by the reader's self-delivered SIGINT; `enter_waiting()` is never called in production; the reader's one-shot behaviour is pinned by `test_process_byte_triggers_on_the_quit_key` and start-once-per-session by `test_quit_listener_lifecycle_wraps_the_turn_loop`.
7. Built and ran MRE `spikes/debug/58-q-interrupt-mid-execution-mre.py` (drives the real `_read_loop` with three queued `q` bytes). Observed: only 1 of 3 presses fired the quit hook — the reader thread exits permanently after the first `q`. REPRODUCED.
8. Zero-Touch Verification: created a shadow replica (`spikes/debug/shadow_terminal_quit_key_listener.py`) whose read loop is PERSISTENT (fires `_trigger` on every `q`, never `break`s) and pointed the MRE at it. Re-ran the MRE: 3/3 presses fired — the MRE PASSES against the shadow, empirically proving the one-shot reader is the defect and that a persistent read loop resolves it (production `src/` untouched).

## Solution

### Root Cause (verified)
The bare-`q` interrupt is a session-lifetime feature: `TerminalQuitKeyListener` is a process-global singleton that the session-loop boundary (`session_cli_handlers._orchestrate_session_loop`) `start()`s ONCE before the turn loop and `stop()`s in the boundary `finally`. Its reader thread, however, was **one-shot**: `_process_byte()` returned `True` on the first `q`, which `break`ed `_read_loop` and **permanently killed the reader**. Two symptoms followed:

1. **`q` mid-execution "ignored"** — the first `q` self-delivers SIGINT; the `InterruptGuard` sets its `interrupted` flag (EXECUTING phase), but the drain only skips actions AFTER the in-flight one, and the in-flight `EXECUTE` runs in its own session (`ShellAdapter` `preexec_fn` → `os.setsid()`) so the SIGINT reaches only the parent — the command runs to completion. For a single/last long action there is nothing left to skip, so nothing visibly changes.
2. **Subsequent `q` dead** — the reader thread was dead for the rest of the session, so no later `q` (planning waits, prompt loops) was ever observed.

Reproduced with `spikes/debug/58-q-interrupt-mid-execution-mre.py` (1/3 `q` presses honored against production) and isolated via a shadow replica with a persistent read loop (3/3) — see Investigation History entries 7–8.

### Fix (Option B — user-selected)
1. **Persistent reader** — make `_read_loop` never `break`: fire `_trigger()` on every `q` and keep polling until `stop()`. (Shadow-verified: 3/3.)
2. **Terminate the in-flight action** — inject the singleton `InterruptGuard` into `ShellAdapter`; while awaiting the child, poll `guard.interrupted` on a config-driven interval and, when set, `os.killpg(child_pid, SIGKILL)` the isolated process group, then return a `ShellOutput` marked `interrupted: True`.
3. **Mark the in-flight action** — `ActionDispatcher` maps the `interrupted` marker to the new `ActionStatus.INTERRUPTED`; the report template renders `- **Status:** INTERRUPTED` verbatim (no template edit needed).
4. **Remaining actions** — stay `SKIPPED` with `INTERRUPT_REASON` (existing drain), preserving the audit trail; `report.md` is still generated.

### Preventative measures (class-level)
- **Resource lifetime must match consumption lifetime.** A one-shot consumer of a session-lifetime resource is a Poka-Yoke violation; the reader now loops until explicitly stopped, and a regression test drives the real `_read_loop` with multiple presses (the MRE scenario, promoted to the suite).
- **Isolated children need group-level termination.** Because EXECUTE children are deliberately detached into their own session, graceful in-flight interruption MUST target the process group (`os.killpg`), not the parent's signal disposition — now the single, documented termination path.
- **Overall status derivation must enumerate the new member.** `ExecutionReportAssembler._determine_overall_status` previously fell through to SUCCESS; it is extended to fold in INTERRUPTED, preventing a purely-interrupted plan from reporting SUCCESS (the class of bug where a new enum member is silently unhandled by an existing switch/derivation).
