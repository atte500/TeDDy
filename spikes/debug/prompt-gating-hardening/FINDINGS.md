# Findings: Prompt Gating Hardening

Prototype for [Slice 00-18 Prompt Gating Hardening](/docs/project/slices/00-18-prompt-gating-hardening.md).
Measured 2026-11-05. The four probes in this directory are run with `uv run python <probe>.py`.

## Technical unknown: does a non-TTY `teddy start` wait for input?

No. It exits on its own, and the terminating component is the handler's empty-message guard, not the ask loop.

### Probe 1 - real CLI with closed stdin (`probe_non_tty_start.py`)

`python -m teddy_executor start` in a fresh temporary project with `stdin=DEVNULL`:

| case | outcome | elapsed |
| --- | --- | --- |
| no `TEDDY_LLM_API_KEY` | exit 1, `Configuration Error: 'llm.api_key' is empty` | 1.59 s |
| dummy `TEDDY_LLM_API_KEY` | reached the opening prompt, exit 1, `Error: No terminal input provided for initial message.` | 1.54 s |

Both cases terminate on their own. In the keyed case the ask loop printed its two prompts (`Response (type 'e' for editor) › ` and `Press [Enter] again to confirm empty response › `) and the handler reported the missing input.

Consequence: without a key, the API-key gate correctly declines to fire because no terminal is attached, so `printf '' | teddy start` stops at configuration validation before the prompt. That is the designed path, not a defect. Manual verification of this slice must supply a key to reach the prompt.

### Probe 2 - `handle_new_session` in process (`probe_handle_new_session.py`)

Fake `ISystemEnvironment` reporting `isatty()=False`, empty `StringIO` stdin, recording `_pt_prompt`, 30 s watchdog:

- outcome: raised `typer.Exit`, `exit_code=1`
- `ISystemEnvironment.isatty` calls: **0**
- ask-loop prompts: 2, both returned `""`
- stderr tail: `Error: No terminal input provided for initial message.`
- watchdog: never fired

The chain is: `handle_new_session` asks because `message is None` → `ConsoleAskLoop.run` reads an empty reply, asks the empty-confirmation question, gets another empty reply and returns `""` → the handler raises `EOFError` and `_handle_startup_error` turns it into `typer.Exit(1)`. `_pt_prompt` catches `EOFError` and returns `""`, so the loop neither raises out of `run()` nor spins; it reads stdin twice and stops.

### Probe 3 - presence source divergence (same script)

One `ConsoleAskLoop` built with a port reporting `isatty()=False`:

- piped stdin → `_is_tty()` False
- TTY-like stdin → `_is_tty()` True

The loop follows `sys.stdin`, not the injected port, so it can disagree with `SessionLifecycleManager._can_prompt_user`.

### What this means for the slice

- The headline symptom (a non-TTY start that waits) does not reproduce today. Gating the handler on presence is hardening: it removes two pointless prompt reads and the prompt text from CI logs, and it avoids creating a session from input that was never read.
- A present-but-blank `-m` on a non-awaiting PENDING_PLAN is the one prompt site that never gates: it never asks, so an interactive or yolo run loses the instruction a human could have given. The slice's Goal covers it; the domain section below records the confirmed fix.
- Routing `ConsoleAskLoop._is_tty()` through `ISystemEnvironment` is still required, on testability and single-source grounds rather than hang prevention.
- Verification must supply a key, otherwise the run stops in preflight.

## Domain unknown: a blank `-m` on a non-awaiting PENDING_PLAN resume

Resolved 2026-11-05 with the user: a blank `-m ""` prompts when a human is reachable, records the reply, and runs the pending plan.

### How the state is produced

Abort a plan at the reviewer: `q` runs `action_cancel` → `self.exit(None)`, so `reviewed_plan is None` → the abort prompt "Plan aborted. How do you want to proceed?" → an empty answer makes `_handle_aborted_session` return `None` → `session_orchestrator.py:349-357` prints "Session terminated." and returns before `finalize_turn` at `:358`. The turn keeps `plan.md`, never gets `report.md`, and carries no `awaiting_reply` flag (that flag is set only by the pipeline MESSAGE stop). Ctrl+C inside the TUI and a crash between the plan write and finalization leave the same shape.

Confirmed on the CLI on 2026-11-05: `teddy start -n -m '<instruction>'`, `q` at the reviewer, Enter at the abort prompt, then `teddy resume -m ''`. The resume printed `Resuming session`, ran the pending plan's EXECUTE actions with no prompt and no reviewer (the run behaved as a yolo resume), and recorded no `## User Request`.

### Today's behaviour (`probe_pending_plan_blank_resume.py` and `probe_pending_plan_message_channel.py`)

- blank `-m ""`: no prompt, bare `execute(plan_path=...)`, no `plan.metadata["user_request"]`.
- non-blank `-m`: no prompt, seeds `plan.metadata["user_request"]`, runs `execute(plan=plan)`.
- absent `-m`: same as blank.
- awaiting-reply pending turn with a blank `-m`: `_consume_awaiting_reply` prompts "The agent is awaiting your reply. How do you want to proceed?".

### Confirmed behaviour

- blank `-m ""` at a terminal: prompt "What would you like to do next?", seed the reply into `plan.metadata["user_request"]`, run the pending plan as its first execution.
- Under yolo the same prompt fires, because the gate reads user presence, not plan approval.
- No terminal: no prompt, bare path unchanged.
- Empty reply: terminate, nothing runs, nothing is seeded.
- The seeded reply reaches the reviewer and the report through the existing channel: `m` writes `user_request` (`textual_plan_reviewer_app.py:397`), the preview reads it back (`textual_plan_reviewer_previews.py:316`), the assembler reads it (`execution_report_assembler.py:38`), and the template renders `## User Request` (`execution_report.md.j2:297-300`). The reviewer submit returns the same plan object (`self.exit(self.plan)`), so a seed made before review survives.
- An awaiting-reply turn keeps its own prompt: the awaiting short-circuit runs before the blank resolution.
- A MESSAGE-only pending plan without the `awaiting_reply` flag can only be classified after a reply exists, so a prompted reply follows the same consume-as-reply path a non-blank `-m` takes.

### Probe results for the one-call fix (`probe_pending_plan_message_channel.py`)

`FixedManager` subclasses the real manager and applies the change: resolve the blank message through `_resolve_blank_message` after the awaiting short-circuit, then re-parse and seed.

| case | prompt | run call | `user_request` |
| --- | --- | --- | --- |
| today: blank `-m ""`, terminal | none | `execute(plan_path=...)` | none |
| today: non-blank `-m`, terminal | none | `execute(plan=plan)` | the message |
| fixed: blank `-m ""`, interactive | one, "What would you like to do next?" | `execute(plan=plan)` | the reply |
| fixed: blank `-m ""`, yolo | one | `execute(plan=plan)` | the reply |
| fixed: blank `-m ""`, no terminal | none | `execute(plan_path=...)` | none |
| fixed: blank `-m ""`, empty reply | one | none (terminates) | — |

### Why not the alternatives

- Prompting needs no new state-machine branch: the reply changes the audit artifact, exactly as the reviewer's `m` key does, so the pending plan still runs. The earlier "supersede and re-plan" concern assumed the reply had to change what executes.
- An error variant would turn a documented idiom ("Pass an empty message to be prompted instead") into a hard failure.
- The README promise needs no change: this slice honours it on the pending branch.

Documented gap, now closed by the slice: the README promised that a blank `-m` prompts; before the fix the pending branch did not honour it.

## Reproduction

~~~~
uv run python spikes/debug/prompt-gating-hardening/probe_non_tty_start.py
uv run python spikes/debug/prompt-gating-hardening/probe_handle_new_session.py
uv run python spikes/debug/prompt-gating-hardening/probe_pending_plan_blank_resume.py
uv run python spikes/debug/prompt-gating-hardening/probe_pending_plan_message_channel.py
~~~~
