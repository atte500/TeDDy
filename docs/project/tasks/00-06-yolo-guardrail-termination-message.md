# Task: YOLO Guardrail Termination Message

## Business Goal

When a YOLO guardrail (`max_turns` or `max_session_cost`) is hit in non-interactive mode, the user must see a clear print/log message explaining why the session was terminated and exactly how to change the settings — while `teddy resume` continues to enforce the limits correctly.

## Context

TeDDy enforces safety limits in `--yolo` / non-interactive mode via `ProductionSessionLoopGuard.should_continue()`. Today, when a limit is exceeded, the guard silently returns `False` and `_orchestrate_session_loop()` in `src/teddy_executor/adapters/inbound/session_cli_handlers.py` simply `break`s — the session ends with no explanation and no hint on how to adjust the limits.

This task changes the `ISessionLoopGuard` contract so `should_continue()` reports *why* it stopped, and makes the shared session loop print/log a user-facing message with settings-change instructions.

### Verified behavior (do NOT change)

- **Resume already respects guardrails.** Both `handle_new_session` and `handle_resume_session` share `_orchestrate_session_loop()`. The loop resolves `initial_turn` from the latest turn folder name and `initial_cost` via `ISessionManager.get_cumulative_cost()`, then instantiates a fresh guard per invocation. Limits are **process-relative**: each `teddy start` / `teddy resume` run starts counting from 0 (Milestone 4: "not cumulative (on `teddy resume`, start counting from 0)").
- **Config keys** (already in `.teddy/config.yaml`): `yolo_guardrails.enabled`, `yolo_guardrails.max_turns` (default 99), `yolo_guardrails.max_session_cost` (default 5.00).
- The guard already owns `IConfigService`, so it can resolve the config file path via `get_config_path()` and embed it in the returned reason.

### Design

- `should_continue()` returns `tuple[bool, str | None]`:
  - `(True, None)` — keep looping (interactive, disabled, or under limits).
  - `(False, reason)` — stop; `reason` names the limit hit, current vs. limit values, and how to change the setting (config key + config file path).
- The loop unpacks the tuple; on stop it logs (`logger.warning`) and prints via `typer.secho`, then breaks.
- All test-harness fakes and unit tests MUST be updated to the tuple contract. The auto-spec harness binds to the protocol signature, but bare mocks without a `side_effect`/`return_value` return a non-iterable `Mock` — any test reaching the loop would crash on tuple unpacking. Run the full suite to catch stragglers.
- Follow Red-Green-Refactor: update/add tests first, watch them fail, then implement.

## Implementation Steps

### Step 1: Update the `ISessionLoopGuard` protocol

- **File:** [src/teddy_executor/core/ports/outbound/session_loop_guard.py](/src/teddy_executor/core/ports/outbound/session_loop_guard.py)
- **Change:** Change the return annotation of `should_continue` from `bool` to `tuple[bool, str | None]` and update the docstring: first element is the continue flag; second is `None` when continuing, or a human-readable reason (which limit, current vs. limit, how to change the setting) when stopping.

### Step 2: Update `ProductionSessionLoopGuard`

- **File:** [src/teddy_executor/core/services/session_loop_guard.py](/src/teddy_executor/core/services/session_loop_guard.py)
- **Change:** Return `(True, None)` for the interactive, disabled, and under-limit paths. On turn-limit stop, return a reason like `"YOLO turn limit reached: {turn_delta}/{max_turns} turns in this run. To change this limit, set 'yolo_guardrails.max_turns' in {config_path}."`. On cost-limit stop, return an analogous reason for `yolo_guardrails.max_session_cost` with costs formatted to 2 decimals (`${cost_delta:.2f}/${max_cost:.2f}`). Resolve `config_path = self._config_service.get_config_path()` only in the failure branches.

### Step 3: Update the session loop call site

- **File:** [src/teddy_executor/adapters/inbound/session_cli_handlers.py](/src/teddy_executor/adapters/inbound/session_cli_handlers.py)
- **Change:** In `_orchestrate_session_loop()` (~line 197), unpack the tuple and print/log on stop:

```python
        cumulative_cost = float(report.metadata.get("cumulative_cost", 0.0))
        should_continue, guard_reason = loop_guard.should_continue(
            turn_count, cumulative_cost, interactive
        )
        if not should_continue:
            reason = guard_reason or "YOLO guardrail limit reached."
            logger.warning("YOLO guardrail hit — session terminated: %s", reason)
            typer.secho(
                f"⚠ YOLO guardrail hit — session terminated.\n{reason}",
                fg=typer.colors.RED,
            )
            break
```

(`logger` and `typer` are already imported at module top; `typer.secho` writes to stdout so the message is also captured by the session Tee into `history.log`.)

### Step 4: Update the test-harness fakes

- **File:** [tests/harness/setup/composition.py](/tests/harness/setup/composition.py)
- **Change:** `TestSessionLoopGuard.should_continue` (~line 143) returns `tuple[bool, str | None]`, e.g. `(should_continue, None if should_continue else "Test YOLO guardrail limit reached.")` where `should_continue = turn_count < max_turns`.
- **File:** [tests/harness/setup/test_environment.py](/tests/harness/setup/test_environment.py)
- **Change:** `_apply_loop_guard_defaults` (~line 234) returns tuples from its `side_effect` lambda using the same pattern.

### Step 5: Update and extend unit tests

- **File:** [tests/suites/unit/core/services/test_session_loop_guard.py](/tests/suites/unit/core/services/test_session_loop_guard.py)
- **Change:** Update all `should_continue` assertions to the tuple contract (continue paths → `== (True, None)`; stop paths → unpack and assert the flag is `False` and the reason mentions the relevant config key). Add tests asserting the reason includes the config file path (set `mock_config.get_config_path.return_value`) and the exact config keys.
- **File:** [tests/suites/unit/adapters/inbound/test_session_replan_loop.py](/tests/suites/unit/adapters/inbound/test_session_replan_loop.py)
- **Change:** Update the two `should_continue.side_effect` lambdas (~lines 72, 128) to return tuples, e.g. `(True, None) if tc < 2 else (False, "max turns reached")`. Add a test (using `capsys`) asserting the termination message is printed when the guard stops the loop, e.g. `"YOLO guardrail" in captured.out`.
- **File:** [tests/suites/unit/adapters/inbound/test_session_start_resequencing.py](/tests/suites/unit/adapters/inbound/test_session_start_resequencing.py)
- **Change:** No code change expected — verify: the loop breaks on `report is None` before `should_continue` is called, so the auto-specced mock is never invoked. Confirm by running the tests.
- **File:** [tests/suites/unit/test_session_loop_guard_harness.py](/tests/suites/unit/test_session_loop_guard_harness.py)
- **Change:** No code change expected — it only asserts the fixture mock is auto-specced. Confirm it still passes.
- **File:** [tests/suites/integration/core/services/test_session_orchestration_integration.py](/tests/suites/integration/core/services/test_session_orchestration_integration.py)
- **Change:** No code change expected — it exercises the handlers but uses the harness fakes updated in Step 4. Confirm via the full suite.

### Step 6: Sync architecture docs

- **File:** [docs/architecture/core/ports/outbound/session_loop_guard.md](/docs/architecture/core/ports/outbound/session_loop_guard.md)
- **Change:** Update the documented signature/return type of `should_continue` to `tuple[bool, str | None]`.
- **File:** [docs/architecture/core/services/session_loop_guard.md](/docs/architecture/core/services/session_loop_guard.md)
- **Change:** Same signature update if it documents the return type.

### Step 7: Document the settings in config.yaml

- **File:** [src/teddy_executor/resources/config/config.yaml](/src/teddy_executor/resources/config/config.yaml)
- **Change:** Expand the `yolo_guardrails` comment to explain the limits and that they are per-run (reset on `teddy resume`):

```yaml
# Safety limits enforced ONLY in --yolo mode. When a limit is hit the session
# is terminated with a message explaining how to adjust these values.
# Limits are per-run: `teddy resume` starts counting from 0 again.
yolo_guardrails:
  enabled: true
  max_turns: 99
  max_session_cost: 5.00
```

## Verification

1. `uv run pytest tests/suites/unit/core/services/test_session_loop_guard.py -q` — all pass with the tuple contract, including the new reason-content assertions.
2. `uv run pytest tests/suites/unit/adapters/inbound/test_session_replan_loop.py tests/suites/unit/adapters/inbound/test_session_start_resequencing.py tests/suites/unit/test_session_loop_guard_harness.py tests/suites/unit/test_environment_harness.py -q` — loop and harness tests pass; the termination-message assertion passes.
3. `grep -rn "should_continue" src/ tests/ --include="*.py"` — every implementation returns and every consumer unpacks the tuple contract (no leftover `-> bool` annotations or bool-returning lambdas).
4. `uv run pytest -q` — full suite green, including the remaining handler tests (`test_session_cli_handlers.py`, `test_session_cli_handlers_resume_meta.py`, `test_bug_24_model_override_on_resume.py`, `test_session_preflight_wiring.py`, `test_session_orchestration_integration.py`). The post-commit hook enforces this too.
5. Manual smoke test (optional): set `yolo_guardrails.max_turns: 1` in `.teddy/config.yaml`, run `teddy start -y`, and confirm the session terminates after one turn with the red ⚠ message including the config key and file path. Restore the config afterward.
