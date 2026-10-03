# Slice: Quit-Key In-Flight Interrupt (Option B)

- **Status:** Planned
- **Milestone:** N/A (ad-hoc)
- **Specs:** [docs/project/specs/interactive-session-workflow.md](/docs/project/specs/interactive-session-workflow.md)
- **Prototype:** N/A (shadow-verified in [Case File 58](/docs/project/debugging/58-q-interrupt-mid-execution.md), MRE `spikes/debug/58-q-interrupt-mid-execution-mre.py`)
- **Component Docs:** [shell_adapter.md](/docs/architecture/adapters/outbound/shell_adapter.md), [execution_report.md](/docs/architecture/core/domain/execution_report.md), [cli.md](/docs/architecture/adapters/inbound/cli.md)
- **Scope Slug:** `quit-key-in-flight-interrupt`

## Business Goal
Make a bare `q` (or Ctrl+C) during plan execution gracefully terminate the IN-FLIGHT action's subprocess, skip the remaining actions, mark the in-flight action `Status: INTERRUPTED` in the generated `report.md`, and keep the session's quit mechanism functional for the rest of the session. Resolves [Case File 58](/docs/project/debugging/58-q-interrupt-mid-execution.md); supersedes the Task-Brief-00-21 "let the in-flight action finish" semantics (user changed the decision to Option B).

## Scenarios

> As a TeDDy user running a long plan, I want to press `q` to stop the currently-running command so that I regain control without losing the audit trail.

```gherkin
Given a session executing a plan whose current action is a long-running EXECUTE
When I press `q`
Then the in-flight EXECUTE subprocess is terminated
And the in-flight action is logged with Status: INTERRUPTED
And the remaining actions are logged as SKIPPED
And report.md is still generated
```

> As a TeDDy user, I want the quit key to keep working after I have already interrupted once, so that I can still exit a later wait window.

```gherkin
Given a session where I have already pressed `q` once during execution
When I press `q` again in a later planning or prompt wait window
Then the session terminates immediately with the interrupt notice
```

> As a TeDDy user running a single-command plan, I want `q` to still be honoured so that a lone long EXECUTE is interruptible.

```gherkin
Given a plan consisting of a single long EXECUTE action
When I press `q`
Then that action is terminated and logged with Status: INTERRUPTED
And report.md is generated with the interrupt audit trail
```

## Edge Cases
- **Grace-window escalation**: If a second `q`/SIGINT arrives within `interrupt.grace_window_seconds`, then the process force-kills immediately, in order to provide an escape hatch for a hung child.
- **Off-TTY listener**: If stdin is not a TTY, then the listener is a no-op, because a bare key cannot be read.
- **TUI review competition**: If the Textual reviewer is running, then it must own stdin (claim `stdin_owned()`), in order that the persistent session-level reader backs off and `q`→cancel is handled by Textual.
- **Prompt input competition**: If a bare `q` arrives while the user is WAITING for input (initial-request ask loop, awaiting-reply prompt, or any `ask_question`), then the reader must NOT consume it (it backs off while `stdin_owned()` is claimed), in order that the user can type the letter `q` into their reply. The initial request is asked before the listener starts (inherently safe); every in-loop prompt must claim `stdin_owned()`.
- **Planning/wait interrupt**: If `q` arrives while nothing is in flight (planning LLM call, prompt), then the session exits immediately with no report, because nothing was mutated.
- **Windows**: If running on Windows, then there is no POSIX process group; termination is best-effort, because there is no `killpg` equivalent.

## Key Unknowns
- [x] [Functional] Overall `RunStatus` for an interrupted plan: resolved (user-approved) — add a new `RunStatus.INTERRUPTED`, mapped with priority FAILURE > INTERRUPTED > SUCCESS > SKIPPED, so a purely-interrupted run no longer falls through to SUCCESS.
- [x] [Functional] Status of the remaining (skipped) actions: resolved (user-approved) — ONLY the in-flight action is logged `INTERRUPTED`; the remaining actions stay `SKIPPED` with `INTERRUPT_REASON` (existing drain behaviour).
- [x] [Technical] TUI/reader stdin race: resolved (user-approved) — the reviewer claims `stdin_owned()` for the duration of `app.run()` so the persistent session-level reader backs off and the TUI `q`→cancel keeps working ("TUI should continue behaving as usual").
- [ ] [Technical] Prompt input competition: the user flagged that while WAITING for user input (the initial-request ask loop, or the awaiting-reply prompt), a bare `q` MUST NOT quit — otherwise the user cannot type the letter `q` into their reply. The reader already backs off while `stdin_owned()` is claimed; the deliverable is to CONFIRM every interactive stdin-read site claims `stdin_owned()` (the initial request is asked before the listener starts, so it is inherently safe; the awaiting-reply prompt runs inside the turn loop where the reader is live).

## Implementation Plan
The fix is layered along the existing Hexagonal seams; NO changes to the inbound ports or the `IShellExecutor.execute` signature are required.

- **Reader persistence (Wiring)**: `TerminalQuitKeyListener._read_loop` currently `break`s when `_process_byte(byte)` returns `True`. Remove the one-shot break so the loop fires `_trigger()` on every `q` and polls until `_stop_event` is set. `_process_byte` becomes side-effect-only (returns `None`). This is the shadow-verified change (`spikes/debug/shadow_terminal_quit_key_listener.py`).
- **In-flight termination (Logic + Seam)**: inject the singleton `InterruptGuard` into `ShellAdapter` (optional constructor param, `None` → today's behaviour for None-guard test sites). In `_run_subprocess`, replace the single blocking `communicate(timeout=...)` with a poll loop bounded by a config-driven interval: `communicate(timeout=interval)` in a loop, and check `guard.interrupted.is_set()` between polls. On set, `os.killpg(process.pid, signal.SIGKILL)` (mirrors `_handle_timeout`) — valid because the child is isolated via `os.setsid()` — then gather partial output and return `ShellOutput` with `interrupted: True` plus an interruption notice in `stdout`.
- **Status mapping (Contract + Logic)**: add `ShellOutput.interrupted: NotRequired[bool]` and `ActionStatus.INTERRUPTED`; `ActionDispatcher._execute_and_process_result` maps the `interrupted` marker → `ActionStatus.INTERRUPTED` (highest precedence for that action).
- **Overall status (Logic)**: extend `ExecutionReportAssembler._determine_overall_status` to add `RunStatus.INTERRUPTED` (user-approved) with priority FAILURE > INTERRUPTED > SUCCESS > SKIPPED, so a purely-interrupted run reports INTERRUPTED instead of falling through to SUCCESS.
- **TUI stdin ownership (Seam)**: the Textual `ReviewerApp.run()` entry claims `stdin_owned()` for its duration so the persistent reader backs off while the TUI owns the keyboard (TUI `q`→cancel keeps working).
- **Prompt stdin ownership (Seam)**: confirm every interactive stdin-read site (the initial-request ask loop, the awaiting-reply prompt, all `ask_question` calls) claims `stdin_owned()` while reading, so a bare `q` typed into a reply is never consumed by the persistent reader (the user's caveat).
- **Config (centralized, no magic numbers)**: add `interrupt.poll_interval_seconds` to `config.yaml` and read it via `IConfigService` (default fallback in the adapter).

Test Harness strategy: unit tests for the killpg path use an in-memory process fake (records `pid`/`killpg`, supports `communicate(timeout=…)` raising `TimeoutExpired`) under `tests/harness/setup/`; behavioral/regression tests bundled with the Wiring deliverable re-use the MRE scenario (drive the REAL `_read_loop` with a multi-press byte source) and the guard-drain suite.

## Deliverables
- [ ] **Contract** - Add `INTERRUPTED = "INTERRUPTED"` to `ActionStatus` in [execution_report.py](/src/teddy_executor/core/domain/models/execution_report.py).
- [ ] **Contract** - Add `interrupted: NotRequired[bool]` to the `ShellOutput` TypedDict in [shell_output.py](/src/teddy_executor/core/domain/models/shell_output.py).
- [ ] **Contract** - Add `RunStatus.INTERRUPTED` (user-approved; mapped FAILURE > INTERRUPTED > SUCCESS > SKIPPED) to `RunStatus` in [execution_report.py](/src/teddy_executor/core/domain/models/execution_report.py).
- [ ] **Harness** - Add an in-memory shell-process fake (records `pid`/`killpg`, `communicate(timeout=…)` raising `TimeoutExpired`) to `tests/harness/setup/` for the ShellAdapter interrupt unit tests.
- [ ] **Harness** - Add `interrupt.poll_interval_seconds` to `config.yaml` and a test-environment default.
- [ ] **Seam** - Inject the singleton `InterruptGuard` into the `IShellExecutor` factory in [infrastructure.py](/src/teddy_executor/registries/infrastructure.py).
- [ ] **Seam** - Make the Textual reviewer claim `stdin_owned()` for the duration of `app.run()` so the persistent quit-key reader backs off.
- [ ] **Seam** - Audit every interactive stdin-read site (initial-request ask loop, awaiting-reply prompt, all `ask_question` calls) to CONFIRM it claims `stdin_owned()` while reading, so the persistent reader never steals a `q` typed into a reply.
- [ ] **Wiring** - Make `TerminalQuitKeyListener._read_loop` persistent (remove the one-shot break) and migrate the two tests that enshrine one-shot behaviour (`test_process_byte_triggers_on_the_quit_key`, `test_read_loop_self_delivers_sigint_on_quit_key`); bundle the multi-press regression test (the MRE scenario promoted to the suite).
- [ ] **Logic** - ShellAdapter: poll `guard.interrupted` while awaiting the child; on set, `os.killpg` the isolated group and return a `ShellOutput` marked `interrupted: True`. Unit tests bundled.
- [ ] **Logic** - `ActionDispatcher._execute_and_process_result`: map the `interrupted` marker → `ActionStatus.INTERRUPTED`. Unit tests bundled.
- [ ] **Logic** - `ExecutionReportAssembler._determine_overall_status`: fold `INTERRUPTED` into the overall derivation. Unit tests bundled.
- [ ] **Migration** - Update `ActionStatus` consumers that enumerate statuses (audit `session_service.py` pruning/state check at ~lines 368-377 for the new member).
- [ ] **Cleanup** - Remove the debug spikes (`spikes/debug/58-q-interrupt-mid-execution-mre.py`, `spikes/debug/shadow_terminal_quit_key_listener.py`) once the slice is verified green.

## Implementation Notes
[To be filled by the Developer.]

## Verification
- [ ] Manual: `teddy start`, run a multi-action plan with a long `EXECUTE` (e.g. `sleep 30`); press `q` → the command is killed, the action shows `- **Status:** INTERRUPTED`, remaining actions show `SKIPPED`, and `report.md` is generated.
- [ ] Manual: in a later turn's wait window, press `q` → the session exits (proving the reader is persistent).
- [ ] Manual: `teddy start`, run a single-action plan (`sleep 30`); press `q` → the lone action shows `Status: INTERRUPTED` and `report.md` is generated.
- [ ] Manual: press `q` during the Textual reviewer → the reviewer's cancel still works (stdin-ownership back-off verified).
- [ ] Manual: press `q` during the planning LLM call / an `ask_question` prompt → immediate exit, no report.
- [ ] Automated: `uv run pytest tests/suites/unit/adapters/outbound/test_terminal_quit_key_listener_reader.py tests/suites/unit/core/services/test_execution_orchestrator_interrupt_drain.py tests/suites/unit/core/services/test_execution_report_assembler.py` — green.
