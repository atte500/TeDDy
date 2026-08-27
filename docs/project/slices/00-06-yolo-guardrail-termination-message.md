# Slice: YOLO Guardrail Termination Message
- **Status:** In Progress
- **Milestone:** N/A (Ad-hoc slice, not tied to active milestone)
- **Specs:** N/A
- **Prototype:** N/A
- **Component Docs:** [Session Loop Guard Port](/docs/architecture/core/ports/outbound/session_loop_guard.md), [Session Loop Guard Service](/docs/architecture/core/services/session_loop_guard.md)
- **Scope Slug:** `yolo-guardrail`

## Business Goal

When a YOLO guardrail (`max_turns` or `max_session_cost`) is hit in non-interactive mode, the user must see a clear print/log message explaining why the session was terminated and exactly how to change the settings — while `teddy resume` continues to enforce the limits correctly.

## Scenarios

> As a user running in `--yolo` mode, I want to see a termination message with the reason and config instructions when a guardrail is hit, so I know what happened and how to adjust the settings.

```gherkin
Given a running non-interactive session
When a YOLO guardrail limit is reached (max_turns or max_session_cost)
Then the session terminates
And a red warning message is printed with:
  - which limit was exceeded (name and current vs. limit)
  - the config key to change
  - the config file path
And the message is also logged via logger.warning
```

## Edge Cases
- **Interactive mode**: No termination message should appear (guard always returns `(True, None)`).
- **Disabled guardrails**: When `yolo_guardrails.enabled` is false, no message should appear.
- **Resume session**: The message should reflect per-run deltas (process-relative baselines captured at loop start).
- **Trivial reason in first deliverable**: Harness fakes use hardcoded reason "Test YOLO guardrail limit reached."; production guard uses "YOLO guardrail limit reached." until the Logic deliverable adds detailed reasons.

## Key Unknowns
- [x] [Technical] All `should_continue` callers: catalogued via `git grep` — 14 occurrences across source, tests, and docs.

## Implementation Plan

The protocol change (`bool -> tuple[bool, str | None]`) is a breaking signature change to a Shared Seam with 14+ consumers. To maintain Green-to-Green atomicity, the work is decomposed into four deliverables:

1. **Contract/Harness/Migration** — Update `ISessionLoopGuard` protocol, update both test-harness fakes (`TestSessionLoopGuard` in `composition.py`, `_apply_loop_guard_defaults` in `test_environment.py`), update `ProductionSessionLoopGuard` to return `(True, None)` / `(False, "YOLO guardrail limit reached.")` (trivial reason), and update all direct consumers/tests to the tuple contract.
2. **Logic** — Implement human-readable reasons in `ProductionSessionLoopGuard` (limit name, current vs. limit, config key + file path) with new unit tests.
3. **Wiring** — Update `_orchestrate_session_loop` to unpack the tuple, log via `logger.warning`, print via red `typer.secho`, and break; add termination-message assertion test.
4. **Documentation** — Sync `docs/architecture/core/ports/outbound/session_loop_guard.md`, `docs/architecture/core/services/session_loop_guard.md`, and expand the `yolo_guardrails` comment in `config.yaml`.

## Deliverables
- [ ] **Contract/Harness/Migration** - Update protocol, test fakes, production guard (trivial reason), and all existing tests to new tuple contract.
- [ ] **Logic** - Implement human-readable reasons in ProductionSessionLoopGuard with new tests.
- [ ] **Wiring** - Update call site to unpack tuple + print termination message; add termination message test.
- [ ] **Documentation** - Sync architecture docs and config.yaml comment.

## Implementation Notes

(To be filled as deliverables are completed.)

## Verification

1. `uv run pytest tests/suites/unit/core/services/test_session_loop_guard.py -q` — all pass with the tuple contract, including new reason-content assertions.
2. `uv run pytest tests/suites/unit/adapters/inbound/test_session_replan_loop.py tests/suites/unit/adapters/inbound/test_session_start_resequencing.py tests/suites/unit/test_session_loop_guard_harness.py tests/suites/unit/test_environment_harness.py -q` — loop and harness tests pass; termination-message assertion passes.
3. `grep -rn "should_continue" src/ tests/ --include="*.py"` — every implementation returns and every consumer unpacks the tuple contract (no leftover `-> bool` annotations or bool-returning lambdas).
4. `uv run pytest -q` — full suite green (post-commit hook enforces this too).
5. Manual smoke test (optional): set `yolo_guardrails.max_turns: 1` in `.teddy/config.yaml`, run `teddy start -y`, confirm the session terminates after one turn with the red ⚠ message including the config key and file path. Restore the config afterward.
