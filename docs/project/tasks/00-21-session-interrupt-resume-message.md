# Task: Session Interrupt, `resume -m` Message Injection & Pipeline Final-Turn Fix

## Business Goal
Make TeDDy sessions safely interruptible without losing the audit trail, enable scripted reply injection via `teddy resume -m`, and fix the `-p` pipeline bug where the final MESSAGE turn incorrectly generates `report.md` and initializes a subsequent turn — leaving the session unresumable in a clean state.

## Context

### Approved Semantics (user-signed off)
1. **Pipeline MESSAGE stop (Workstream A):** When a `-p` session's turn ends with a MESSAGE action, the turn must NOT be finalized: no `report.md`, no next-turn directory (`02/`). The turn's `meta.yaml` gets an `awaiting_reply: true` flag. The session is then resumable via `teddy resume` / `resume -m`.
2. **Ctrl+C during execution (Workstream C, any mode incl. `-p`):** Two-phase graceful interrupt. An interrupt flag is set; the in-flight action (including a running shell command) is allowed to finish; remaining actions are skipped and logged as INTERRUPTED; `report.md` IS still generated with the full audit trail; the process then exits. A second Ctrl+C escalates to immediate force-kill (escape hatch for hung commands).
3. **Ctrl+C while waiting (Workstream C):** While waiting for a user reply (any `ask_question` prompt) OR while waiting for the LLM reply (planning phase), Ctrl+C exits IMMEDIATELY — nothing is in flight, nothing to preserve.
4. **`teddy resume -m` (Workstream B):**
   - Latest turn HAS `report.md` → append a `## User Request` section to the report (smart-fenced codeblock, identical format to a normal user request), then transition to the next turn and plan with the message, skipping the interactive prompt.
   - Latest turn has NO `report.md` (pipeline MESSAGE turn, awaiting-reply flag) → the message becomes the user's reply: the state machine must NOT re-execute the plan; it transitions to the next turn and plans with the message.
   - Interactive `resume` (no `-m`) of an awaiting-reply turn → prompt for the reply, mirroring the existing abort flow (`_handle_aborted_session`).

### Root Cause (Workstream A) — verified by code tracing + real session artifacts
In `SessionOrchestrator.execute()`, `self._lifecycle_manager.finalize_turn(plan_path, report, plan=plan)` runs UNCONDITIONALLY whenever `is_session and plan_path` — writing `report.md` AND creating the next turn directory — before the CLI-layer loop (`_orchestrate_session_loop`) ever checks for the pipeline MESSAGE break. Evidence: session `20261001_180654-heylo` shows `01/report.md` (containing the agent's message) plus an initialized, empty `02/`. Case Files 42/43 only fixed MESSAGE dispatch (`ActionExecutor.confirm_and_dispatch` short-circuit) and terminal printing (`--- MESSAGE from TeDDy ---`); the persistence semantics were never addressed. Note the precedent: Bug 15's empty-message termination already returns `None` without a report — a similar early-return path is needed here.

### Signal-Handling Feasibility (Workstream C) — empirically validated via spike (spike since removed; findings recorded here)
- A custom SIGINT handler overrides the default kill: the parent survived a process-group-wide SIGINT (what a real terminal Ctrl+C delivers) and still set the interrupt flag while `subprocess.run` was in flight.
- Raising `KeyboardInterrupt` from the handler cleanly breaks blocking waits (immediate-exit path confirmed).
- CRITICAL nuance: an unshielded child process is killed by the terminal's group-wide SIGINT (returncode -2). Shell commands MUST be launched in their own process group (`start_new_session=True` on POSIX) so "the in-flight action finishes" holds for long-running `EXECUTE` actions. Windows has no POSIX process groups: best-effort, flag-based graceful handling only.
- Design: handler inspects the current phase. Phase WAITING (prompts, LLM planning call) → raise `KeyboardInterrupt`. Phase EXECUTING → set a `threading.Event` flag. A second SIGINT within the grace window force-escalates.

### State-Machine Consequence (Workstream B)
`SessionService.get_session_state` classifies a turn with `plan.md` but no `report.md` as `PENDING_PLAN`, and `SessionLifecycleManager.resume` would re-execute that plan. With Workstream A in place, this is WRONG for awaiting-reply turns. The state detection MUST consult the `awaiting_reply` meta flag: such turns are a new logical state (AWAITING_REPLY), not PENDING_PLAN.

### Relevant Existing Code Touch Points
- `src/teddy_executor/core/services/session_orchestrator.py` — `execute()` turn transition, `_handle_aborted_session`, pipeline MESSAGE printing block.
- `src/teddy_executor/core/services/session_lifecycle_manager.py` — `resume()` state machine (`PENDING_PLAN` / `EMPTY` / `COMPLETE_TURN` branches).
- `src/teddy_executor/core/services/session_service.py` — `get_session_state` (state classification; also detects user-request turns via `## User Request` heading regex at ~line 339).
- `src/teddy_executor/core/services/session_repository.py` — `save_meta` / `load_meta` for the `awaiting_reply` flag.
- `src/teddy_executor/core/services/execution_orchestrator.py` — action loop; `_handle_aborted_execution` precedent.
- `src/teddy_executor/adapters/outbound/shell_adapter.py` — subprocess launch (needs `start_new_session`).
- `src/teddy_executor/adapters/inbound/session_cli_handlers.py` — `handle_resume_session` (~line 525), `_orchestrate_session_loop`, `handle_new_session`.
- `src/teddy_executor/__main__.py` — `resume()` command (~line 385).
- `src/teddy_executor/core/services/templates/execution_report.md.j2` — `## User Request` section format (~line 130).
- `src/teddy_executor/core/utils/markdown.py` — existing smart-fencing helpers (see also `tests/suites/unit/core/services/test_report_message_fencing.py`).
- Architectural constraints: Constructor Injection only (no global state / module patching — the interrupt guard must be injected, e.g., composed at the CLI handler and passed down); centralized config for any new tunables; no silent error suppression.

### Order of Work
Workstreams are ordered A → B → C. A is the defect fix and defines the awaiting-reply state B depends on. C is independent but largest.

---

## Implementation Steps

### Step 1: Suppress turn finalization for pipeline MESSAGE turns
- **File:** [src/teddy_executor/core/services/session_orchestrator.py](/src/teddy_executor/core/services/session_orchestrator.py)
- **Change:** In `execute()`, guard the `if is_session and plan_path:` turn-transition block. When `pipeline` is True AND the plan is a communication turn with a non-empty MESSAGE in `report.action_logs` (same detection pattern as the existing "4a. Empty user reply" block and the CLI pipeline break): (1) skip `self._lifecycle_manager.finalize_turn(...)` entirely — no `report.md`, no `T_next`; (2) load the current turn's `meta.yaml` via the session repository, set `awaiting_reply: true`, and `save_meta`; (3) keep the existing `--- MESSAGE from TeDDy ---` terminal printing and return the report so the CLI loop's existing MESSAGE break fires. Ensure the `awaiting_reply` flag is cleared whenever the turn is later resolved (see Step 5).

### Step 2: Regression tests for pipeline MESSAGE suppression
- **File:** [tests/suites/unit/core/services/test_pipeline_message_break.py](/tests/suites/unit/core/services/test_pipeline_message_break.py)
- **Change:** Add tests asserting that with `pipeline=True` and a MESSAGE-turn report: `finalize_turn` is NOT called, no next turn directory is created, the current turn's `meta.yaml` contains `awaiting_reply: true`, and the report is still returned. Add a companion test that non-pipeline MESSAGE turns still finalize normally.

### Step 3: Add `--message/-m` flag to the `resume` command
- **File:** [src/teddy_executor/__main__.py](/src/teddy_executor/__main__.py)
- **Change:** Add `message: Optional[str] = typer.Option(None, "--message", "-m", help="Inject a user request/reply without interactive prompting.")` to `resume()` (~line 385) and pass `message=message` to `handle_resume_session`.

### Step 4: Thread `message` through the resume CLI handlers
- **File:** [src/teddy_executor/adapters/inbound/session_cli_handlers.py](/src/teddy_executor/adapters/inbound/session_cli_handlers.py)
- **Change:** Add `message: Optional[str] = None` to `handle_resume_session` and `_orchestrate_session_loop`; pass it into the orchestrator resume chain (`SessionOrchestrator.resume` → `SessionLifecycleManager.resume`). Do not prompt for a new message when one was injected.

### Step 5: Extend the resume state machine for awaiting-reply turns
- **File:** [src/teddy_executor/core/services/session_lifecycle_manager.py](/src/teddy_executor/core/services/session_lifecycle_manager.py) and [src/teddy_executor/core/services/session_service.py](/src/teddy_executor/core/services/session_service.py)
- **Change:** In state classification (`get_session_state`) or at the top of `SessionLifecycleManager.resume`, detect the awaiting-reply state: latest turn has `plan.md`, NO `report.md`, and `meta.yaml` contains `awaiting_reply: true`. In that state: (a) do NOT re-execute the plan; (b) if a message was injected (`resume -m`) → clear the flag and transition to the next turn, planning with the injected message; (c) if interactive and no message → prompt for the reply (mirroring `_handle_aborted_session`'s "How do you want to proceed?" flow), then transition and plan; (d) if non-interactive with no message → exit cleanly with guidance. Ensure `COMPLETE_TURN` resume with an injected message also skips the interactive prompt and plans with the message.

### Step 6: Append smart-fenced `## User Request` to an existing report
- **File:** [src/teddy_executor/core/services/session_lifecycle_manager.py](/src/teddy_executor/core/services/session_lifecycle_manager.py)
- **Change:** When resuming a `COMPLETE_TURN` with an injected message, append a `## User Request` section to the latest turn's `report.md` BEFORE transitioning, matching the format of the `## User Request` section in `execution_report.md.j2` (~line 130): the message body wrapped in a smart-fenced codeblock (fence length = longest backtick run in the content + 1). Reuse the existing smart-fencing helper from `core/utils/markdown.py`; extend it if it only covers tildes/backticks asymmetry and not longest-run computation. Verify `session_service`'s user-request-turn detection regex (`^## User Request`) matches the appended section.

### Step 7: Implement the interrupt guard
- **File:** [src/teddy_executor/core/utils/interrupt_guard.py](/src/teddy_executor/core/utils/interrupt_guard.py) (new)
- **Change:** Create an `InterruptGuard` class: installs the process SIGINT handler; exposes `enter_waiting()` / `enter_executing()` phase setters (context managers); exposes an `interrupted` `threading.Event`. Handler behavior: in WAITING phase → raise `KeyboardInterrupt`; in EXECUTING phase → set the flag (first signal) or re-raise/force-kill (second signal within the grace window). Centralize the grace-window duration in the configuration layer (no magic numbers). Keep the core module import-free of DI frameworks; inject the guard explicitly from the CLI handler / composition root.

### Step 8: Wire phases and graceful drain into execution
- **File:** [src/teddy_executor/core/services/execution_orchestrator.py](/src/teddy_executor/core/services/execution_orchestrator.py), [src/teddy_executor/adapters/inbound/session_cli_handlers.py](/src/teddy_executor/adapters/inbound/session_cli_handlers.py)
- **Change:** Set WAITING phase around all `ask_question` prompts and the planning-phase LLM call (immediate-exit path: catch `KeyboardInterrupt` at the session-loop boundary, print a short termination notice, exit without report — nothing mutated). Set EXECUTING phase around the action dispatch loop; after each action completes, check `guard.interrupted`: if set, mark all remaining actions as SKIPPED/INTERRUPTED with reason "Interrupted by user (Ctrl+C)." and exit the loop normally so `report.md` is generated through the existing `finalize_turn` path with the full audit trail. Do not swallow the KeyboardInterrupt silently — log context per Failure Transparency.

### Step 9: Shield in-flight shell commands from terminal SIGINT
- **File:** [src/teddy_executor/adapters/outbound/shell_adapter.py](/src/teddy_executor/adapters/outbound/shell_adapter.py)
- **Change:** Launch EXECUTE subprocesses with `start_new_session=True` on POSIX so a terminal Ctrl+C does not kill the child mid-run (the in-flight action must complete per approved semantics). On Windows, document best-effort flag-based graceful handling (no process groups). Mind the existing `cmd /c` Windows isolation decision in ARCHITECTURE.md.

### Step 10: Tests for interrupt and resume -m behavior
- **File:** [tests/suites/unit/core/utils/test_interrupt_guard.py](/tests/suites/unit/core/utils/test_interrupt_guard.py) (new), [tests/suites/unit/core/services/test_session_lifecycle_manager.py](/tests/suites/unit/core/services/test_session_lifecycle_manager.py)
- **Change:** Unit-test `InterruptGuard` phase behavior (WAITING raises, EXECUTING sets flag, double-signal escalates) — use `os.kill` self-signaling per the validated spike pattern, marked to skip on platforms where signal delivery is unreliable in CI. Unit-test the extended state machine: awaiting-reply turn + `-m` → no re-execution, transitions, plans with message; awaiting-reply + interactive → prompts; `COMPLETE_TURN` + `-m` → smart-fenced `## User Request` appended and prompt skipped.

---

## Verification

1. `uv run pytest tests/suites/unit/core/services/test_pipeline_message_break.py tests/suites/unit/core/services/test_session_lifecycle_manager.py tests/suites/unit/core/utils/test_interrupt_guard.py` — all green.
2. Full suite green via the post-commit hook (never bypassed).
3. Manual: `teddy start -a assistant -p -m "Say hi and ask how I am"` → process exits after the MESSAGE; `.teddy/sessions/<name>/01/` contains NO `report.md`, no `02/` directory; `01/meta.yaml` has `awaiting_reply: true`.
4. Manual: `teddy resume -m "I am great, tell me a joke"` on that session → turn 01 is NOT re-executed; `02/` is created and planned with the injected reply.
5. Manual: `teddy resume -m "new request"` on a fully completed session → `## User Request` appended to the latest `report.md` with a smart-fenced codeblock; next turn planned without interactive prompt; `session_service` recognizes it as a user-request turn.
6. Manual: `teddy start` (interactive), Ctrl+C during a multi-action plan with a long `EXECUTE` (e.g., `sleep 5`) → command completes, remaining actions logged as INTERRUPTED, `report.md` created, process exits. Second Ctrl+C during the sleep → immediate kill.
7. Manual: Ctrl+C during the planning LLM call and during any `ask_question` prompt → immediate exit, no partial artifacts.
