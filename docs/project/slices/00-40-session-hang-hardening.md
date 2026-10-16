# Slice: Session-Hang Preventative Hardening (Over-Budget Guardrail & Ctrl+C ISIG)
- **Status:** In Progress
- **Milestone:** N/A (ad-hoc)
- **Depends On:** None
- **Specs:** None
- **Prototype:** N/A
- **Component Docs:** [docs/architecture/core/services/planning_service.md](/docs/architecture/core/services/planning_service.md)
- **Scope Slug:** `hang-hardening`

## Business Goal
Harden the interactive session against the two residual failure modes from case file 07. An over-budget request must fail loudly instead of stalling silently, and Ctrl+C must reach the process by keeping the terminal ISIG flag enabled. Both changes convert a silent failure into a visible, diagnosable one.

## Scenarios
> As a session user, I want an over-budget request to produce a clear error so that a silent stall becomes a diagnosable failure.

```gherkin
Given an assembled request whose token count exceeds the model's context window
When the planning service prepares the LLM call
Then it raises a clear, user-visible error naming the token count and the window
And the session does not stall silently
```

> As a session user, I want Ctrl+C to interrupt an in-flight turn so that I can stop a long or stalled operation.

```gherkin
Given a component previously cleared the terminal ISIG flag
When the quit-key listener enters non-canonical mode
Then ISIG is enabled so a real Ctrl+C generates SIGINT
```

## Edge Cases
- **Unknown context window**: If `get_context_window(model)` returns a non-positive value, then no error is raised, because the window is unknown and a false positive blocks legitimate work.
- **Exact boundary**: If `token_count` equals the context window, then no error is raised, because only a strict excess is over budget.
- **Over budget**: If `token_count` exceeds the context window, then a clear error names both numbers and the model.
- **ISIG inherited clear**: If ISIG is clear on entry to `_enter_noncanonical_mode`, then the method sets it, because a prior raw-mode component (prompt_toolkit) can clear it and leave the terminal unable to generate SIGINT.
- **ISIG already set**: If ISIG is already set, then the method leaves it set, because the change is idempotent.
- **No raw-mode regression**: If `_enter_noncanonical_mode` runs, then ICANON and ECHO remain cleared, because the bare-`q` listener needs non-canonical input.

## Key Unknowns
- [x] [Domain] Error surfacing path: the guardrail must produce a user-visible error, not a traceback. Resolved by inspection: `PlanningService._run_preflight_check` already raises `ConfigurationError`, the established user-visible path, so reuse needs no new wiring.
- [x] [Technical] ISIG assertion seam: resolved by inspection: the existing terminal tests inject a fake `termios` module, so the flag is assertable without a real TTY.

## Impact
Surface of affected components using the Parallel Change model. The two changes are additive and non-breaking, so no expand-migrate-contract cycle is required.

1. `[EXPAND]` `PlanningService.generate_plan` — add an over-budget guardrail before the LLM generation call; no signature change.
2. `[EXPAND]` `TerminalQuitKeyListener._enter_noncanonical_mode` — set the `ISIG` flag in addition to clearing `ICANON` and `ECHO`; no signature change.
3. `[CONTRACT]` None — no shared contract is removed or changed.

## Deliverables
- [x] **Wiring** — Connect the over-budget guardrail end-to-end: add a minimal guardrail in `PlanningService.generate_plan` that raises when `token_count` exceeds `get_context_window(model)`, and an acceptance test that drives the session boundary with an over-budget double and asserts a user-visible error.
- [x] **Logic** — Harden the context-budget guardrail: unit tests for the non-positive window, exact-boundary, and over-budget cases, plus a clear error message. Reuse the existing `ConfigurationError` type.
- [ ] **Logic** — Re-enable `ISIG` in `TerminalQuitKeyListener._enter_noncanonical_mode`: unit tests assert `ISIG` is set regardless of inherited state and that `ICANON` and `ECHO` stay cleared.
- [ ] **Cleanup** — Update the `planning_service` component doc, record the delivered measures in the case file, and resolve the stale case-file header link.

## Implementation Notes

### Wiring (deliverable 1) — over-budget guardrail end-to-end

- **Guardrail location:** `PlanningService.generate_plan`, inserted immediately after the telemetry display and before the `_perform_generation_with_retry` call. It computes `context_window = int(self._safe_float(self._llm_client.get_context_window(model=model)))` and raises when `context_window > 0 and token_count > context_window`. The strict `>` and the `> 0` guard already satisfy the exact-boundary and unknown-window edge cases; the Logic deliverable pins them with unit tests.
- **Error type:** reused `ConfigurationError`, imported function-locally. `_run_preflight_check` already raises the same type from the same function, so the established user-visible path needs no new wiring: the CLI boundary `_handle_startup_error` prints `Error: {error}` plus the config-path hint, then raises `typer.Exit(code=1)`.
- **Message:** `Context Window Exceeded: the request is {token_count} tokens, which exceeds the {context_window}-token context window of model '{model}'.` It names both numbers and the model.
- **Surfacing path:** `SessionPlanner.trigger_new_plan` calls `generate_plan`; `_orchestrate_session_loop` guards the turn body with `except KeyboardInterrupt` only, so the raised `ConfigurationError` propagates to the outer `except Exception as e: _handle_startup_error(container, e)` block.
- **Red evidence (turn 103):** `tests/suites/acceptance/test_over_budget_guardrail.py` drove `CliTestAdapter.run_start` with `get_token_count` 200_000 and `get_context_window` 128_000. It failed with `assert 0 != 0` because no guardrail existed and the session stalling path exited code 0.
- **Green evidence (turn 104):** the same test reported `1 passed`. It asserts `result.exit_code != 0`, `Context Window Exceeded`, `200000`, `128000`, and `mock_llm_client.get_completion.assert_not_called()`.
- **Integration evidence (turn 105):** `make test` reported `1808 passed, 5 skipped`, proving the additive guardrail caused no regression.

### Logic (deliverable 2) — context-budget guardrail edge cases

- **Test file:** `tests/suites/unit/core/services/test_planning_service_context_budget.py`, four tests in the pinned-matrix style.
- **Seam:** the tests drive the extracted `PlanningService._check_context_budget(token_count, model)` helper directly, mirroring the established `test_run_preflight_check_raises_on_error` precedent. This is a Logic deliverable that pins behaviour the Wiring helper already encoded, so no production change was needed.
- **Construction:** resolved the service via `env.get_service(PlanningService)` and injected an auto-specced `ILlmClient` double via `env.mock_port(ILlmClient)`. No global patching and no bare mock objects.
- **Edge cases pinned:** over-budget (`window + 1`) raises `ConfigurationError`; exact boundary (`token_count == window`) does not raise; zero window (unknown) does not raise; negative window (unknown) does not raise.
- **Message assertions:** the over-budget test asserts `Context Window Exceeded`, the request count, the window count, and the model name all appear in the error.
- **Red evidence (turn 113):** all four tests passed on the first run (`4 passed in 1.18s`). The Red step was a confirming run rather than a failing one, because the helper already satisfied the edge-case contract.
- **Integration evidence (turn 114):** `make test` reported `1812 passed, 5 skipped`, proving the new unit tests integrate cleanly.

## Verification
- [ ] **Over-budget guardrail surfaces a visible error:**
    Add a large file to `.teddy/session.context` and set `llm.model` to a model with a small context window, then run `teddy start -m "hello"`.
    Verify the session prints an error naming the token count and the context window, and does not stall silently.
- [ ] **Ctrl+C delivers SIGINT:**
    Run `teddy start -m "<a request that triggers a long turn>"`, then press `Ctrl+C` during the turn.
    Verify the turn interrupts cleanly and the session returns to the prompt.
