# Slice: Session Termination & Interrupt Messaging Refinements
- **Status:** In Progress
- **Milestone:** N/A
- **Specs:** N/A
- **Prototype:** N/A
- **Component Docs:** [SessionOrchestrator](/docs/architecture/core/services/session_orchestrator.md)
- **Scope Slug:** `session-notices`

## Business Goal

Make every session-termination and interrupt notice consistent, actionable, and self-explanatory: the resume hint is simplified to `teddy resume`, the interrupt notice names the exact key the user pressed (`q` or `Ctrl+C`), and each notice renders as a single yellow line so the user always sees one clear next step.

## Scenarios

> As a user, I want the interrupt notice to tell me which key I pressed and how to continue.

```gherkin
Feature: Interrupt notice names the key and shows the resume hint on one yellow line
  Scenario: Bare `q` during a turn
    Given a session is executing a turn
    When the user presses `q`
    Then the terminal shows "Interrupted by user (q). To continue the session, use `teddy resume`." in yellow on one line

  Scenario: Ctrl+C while idle
    Given a session is idle (waiting at a prompt or planning)
    When the user presses Ctrl+C
    Then the terminal shows "Interrupted by user (Ctrl+C). To continue the session, use `teddy resume`." in yellow on one line
```

> As a user, I want termination notices to be yellow and give me the next step on the same line.

```gherkin
Feature: Termination notices are yellow and single-line
  Scenario: Empty message termination
    Given a communication turn whose user reply is empty
    When the turn completes
    Then the terminal shows "Session terminated (empty message). To continue the session, use `teddy resume`." in yellow on one line

  Scenario: Aborted session termination
    Given the session is aborted
    When the turn completes
    Then the terminal shows "Session terminated. To continue the session, use `teddy resume`." in yellow on one line
```

## Edge Cases

- **Unset interrupt source**: If the guard's source marker is unset (a genuine Ctrl+C, or a test that sets `interrupted` directly), the notice defaults to `(Ctrl+C)`.
- **YOLO guardrail limit**: The guardrail-limit notice (`_emit_guard_termination`) stays RED and is NOT merged with the resume hint — it is a hard stop, not an interruption.
- **Audit-trail reason unchanged**: `INTERRUPT_REASON` ("Interrupted by user.") remains the single source for the report skip reason; only the boundary notice adds the key tag and hint.
- **Exit stream unchanged**: Termination notices stay on stderr (`err=True`); interrupt notices stay on stdout — no test-stream churn.

## Key Unknowns

- [x] [Technical] How to convey the pressed key (`q` vs `Ctrl+C`) from the quit-key reader thread to the notice site, given both converge on SIGINT? Resolved: record the source on the shared `InterruptGuard` singleton (the one object both the boundary and the notice sites resolve) from the listener's `on_quit` callback, before it self-delivers SIGINT. Design Sensitivity: no new port is required; if the guard could not carry the marker, a new seam would be needed.
- [x] [Functional] One combined line vs. two lines? Resolved: one line (notice + hint merged).
- [x] [Functional] Keep the `(q)`/`(Ctrl+C)` key tag? Resolved: keep it (deliberately reverses the Bug 56 "(Ctrl+C)" removal, now that the source is accurate).

## Scope & Impact

- `[NEW]` `core/utils/session_notices.py` — single source for the resume hint and the notice-composition helpers.
- `[EXPAND]` `InterruptGuard` — additive `source` marker + `record_source()` (no signature change to `install()` or the phase managers).
- `[EXPAND]` `container` `IQuitKeyListener` factory — inject an `on_quit` callback that records `q` on the guard, then self-delivers SIGINT.
- `[MIGRATE]` `session_cli_handlers._orchestrate_session_loop` — two interrupt notice sites (interrupt drain + `KeyboardInterrupt`).
- `[MIGRATE]` `session_orchestrator.execute` — two termination notice sites (empty message + aborted).
- `[MIGRATE]` `tests/suites/unit/adapters/inbound/test_session_loop_interrupt_wiring.py` — update the notice assertion.

**Impact Notes:** `InterruptGuard` is a documented singleton exception to the transient-scope rule, so the source marker is shared by the boundary and the notice sites with no scope churn. `INTERRUPT_REASON` has two consumers (audit trail + boundary notice) but is NOT modified. The container factory change touches only the `IQuitKeyListener` composition; the listener's `on_quit=None` default path is unchanged.

## Deliverables

- [x] **Wiring** - End-to-end key-tagged interrupt notice: add the `source` marker + `record_source()` to `InterruptGuard`; wire the container's `IQuitKeyListener` factory to record `q` before self-delivering SIGINT; render the interrupt notice at both session-loop sites as one yellow line naming the key (`guard.source or "Ctrl+C"`) plus the shared `RESUME_HINT`. Introduce `RESUME_HINT` (single source). Update the existing interrupt-wiring test in the same change set to keep green.
- [x] **Logic** - Recolor and simplify both `session_orchestrator` termination notices (empty-message and aborted) to one yellow line ending with the shared `RESUME_HINT`.
- [ ] **Harness** - Regression tests: the interrupt notice names `q` (via the listener/guard seam) and `Ctrl+C` (default); the termination notices are yellow, single-line, and carry the simplified hint.

## Implementation Notes

### Wiring (key-tagged interrupt notice)

- **New `core/utils/session_notices.py`** is the single source for the shared resume hint (`RESUME_HINT = "To continue the session, use \`teddy resume\`."`), the `Ctrl+C` default key label (`DEFAULT_INTERRUPT_KEY`), and the composer `format_interrupt_notice(source)`. The composer derives its prefix from `INTERRUPT_REASON.removesuffix(".")` so the boundary notice and the audit-trail skip reason stay byte-locked; it renders `"Interrupted by user (<key>). <RESUME_HINT>"` on one line, defaulting `<key>` to `Ctrl+C` when no source was recorded.
- **`InterruptGuard`** gained an additive `source: Optional[str]` field (default `None`) and `record_source(source)`. `install()` and the phase context managers are untouched, so the WAITING/EXECUTING contract is unchanged.
- **Container composition root** now injects an `on_quit` hook into the `IQuitKeyListener` factory via `_record_quit_source(container)`: it records `"q"` on the shared `InterruptGuard` singleton, THEN `os.kill`s the process with SIGINT. The self-delivery is required because `TerminalQuitKeyListener._trigger` returns after invoking a supplied `on_quit` callback; the self-delivered SIGINT drives the guard's already-tested branch unchanged. The `on_quit=None` default path in the listener is unchanged.
- **`session_cli_handlers._orchestrate_session_loop`** renders `format_interrupt_notice(interrupt_guard.source)` at BOTH interrupt sites (the graceful-drain branch and the `KeyboardInterrupt` catch), both on stdout in yellow. The now-unused `INTERRUPT_REASON` import was dropped from this module.
- **Test updates:** `tests/suites/unit/adapters/inbound/test_session_loop_interrupt_wiring.py` was updated in the same change set — the pre-existing `"(Ctrl+C)" not in captured.out` assertion directly contradicted the new notice, so it was replaced with the combined-notice assertion, and a new `test_session_loop_names_the_quit_key_when_recorded` case pins the `q`-source path. Focused run: 5 passed; Integration `make test`: 1753 passed, 5 skipped.

### Logic (termination notices)

- **`core/utils/session_notices.py`** gained a second composer, `format_termination_notice(reason)`, alongside `format_interrupt_notice`: it returns `f"{reason} {RESUME_HINT}"`, appending the SAME shared hint so every notice — interrupt or termination — ends with the identical actionable next step. The situation lead-in is passed in by the caller so one helper serves both termination sites.
- **`session_orchestrator.execute`** now calls `format_termination_notice(...)` at BOTH termination sites, each as exactly ONE `typer.secho(..., fg=typer.colors.YELLOW, err=True)` call: the empty-message termination (`"Session terminated (empty message)."`) and the aborted-session termination (`"Session terminated."`). The previous two-line RED form — a leading-`"\n"` situation line plus a bare-hint line — was removed from both sites, and the retired literal ``"To continue the session, use `teddy resume [session_path]`."`` is gone from this module.
- **Stream unchanged:** both notices stay on STDERR (`err=True`); only the color (RED→YELLOW) and the two-line→one-line collapse changed, so the exit-stream contract holds.
- **Non-breaking:** `test_bug_15_empty_message_termination.py:136` only substring-checks the lead-in `"Session terminated (empty message)."` (preserved), and `test_abort_handling_regression.py` asserts only `result is None` / `finalize_turn` — neither pins color, line count, or the retired hint, so no existing test needed updating in this change set.
- **New test file:** `tests/suites/unit/core/services/test_session_termination_notices.py` pins the composer directly and drives the real `execute` empty-message and aborted paths (recording `typer.secho` calls) to assert each notice is ONE yellow stderr line ending with the hint. Focused run: 3 passed; Integration `make test`: 1756 passed, 5 skipped.

## Verification

- [ ] Start a session, press `q`, and verify the terminal shows `Interrupted by user (q). To continue the session, use teddy resume.` in yellow on one line.
- [ ] Start a session, press Ctrl+C while idle, and verify the terminal shows `Interrupted by user (Ctrl+C). To continue the session, use teddy resume.` in yellow on one line.
- [ ] Trigger an empty-message termination and verify the terminal shows `Session terminated (empty message). To continue the session, use teddy resume.` in yellow on one line.
- [ ] Trigger an aborted-session termination and verify the terminal shows `Session terminated. To continue the session, use teddy resume.` in yellow on one line.
- [ ] Verify the YOLO guardrail-limit notice remains red.
- [ ] Full suite green (`make test`).
