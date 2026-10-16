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
- [ ] **Wiring** — Connect the over-budget guardrail end-to-end: add a minimal guardrail in `PlanningService.generate_plan` that raises when `token_count` exceeds `get_context_window(model)`, and an acceptance test that drives the session boundary with an over-budget double and asserts a user-visible error.
- [ ] **Logic** — Harden the context-budget guardrail: unit tests for the non-positive window, exact-boundary, and over-budget cases, plus a clear error message. Reuse the existing `ConfigurationError` type.
- [ ] **Logic** — Re-enable `ISIG` in `TerminalQuitKeyListener._enter_noncanonical_mode`: unit tests assert `ISIG` is set regardless of inherited state and that `ICANON` and `ECHO` stay cleared.
- [ ] **Cleanup** — Update the `planning_service` component doc, record the delivered measures in the case file, and resolve the stale case-file header link.

## Implementation Notes
Filled during implementation. Decisions and discoveries are recorded here.

## Verification
- [ ] **Over-budget guardrail surfaces a visible error:**
    Add a large file to `.teddy/session.context` and set `llm.model` to a model with a small context window, then run `teddy start -m "hello"`.
    Verify the session prints an error naming the token count and the context window, and does not stall silently.
- [ ] **Ctrl+C delivers SIGINT:**
    Run `teddy start -m "<a request that triggers a long turn>"`, then press `Ctrl+C` during the turn.
    Verify the turn interrupts cleanly and the session returns to the prompt.
