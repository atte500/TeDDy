# Slice: Configurable Guardrails
- **Status:** In Progress
- **Milestone:** N/A (ad-hoc slice)
- **Depends On:** N/A
- **Specs:** N/A
- **Prototype:** N/A
- **Component Docs:** [SessionLoopGuard](/docs/architecture/core/services/session_loop_guard.md), [ConfigService](/docs/architecture/core/ports/outbound/config_service.md)
- **Scope Slug:** `guardrails`

## Business Goal
Bound the cost and duration of every non-interactive run and let operators tune those bounds per environment. Rename the misleading `yolo_guardrails` namespace to `guardrails`, because the limits apply to every non-interactive run, not only `--yolo`.

## Scenarios

> As an operator, I want a non-interactive run to stop after a configurable number of turns or dollars, so that a runaway loop cannot consume unbounded budget.

```gherkin
Given a non-interactive run reaches the configured turn limit
When the loop guard evaluates the next turn
Then the session terminates with a message that names the limit and the config file
```

> As an operator, I want to override the limits from the environment, so that CI jobs tune them without editing `.teddy/config.yaml`.

```gherkin
Given TEDDY_MAX_TURNS is set and no CLI flag overrides it
When the loop guard resolves the turn limit
Then the guard uses the environment value instead of the config value
```

> As an operator, I want each message turn to grant a fresh budget, so that every human-approved segment gets its own allowance.

```gherkin
Given guardrails.message_reset is true and a message turn completes with a non-empty reply
When the session continues to the next turn
Then the turn and cost baselines re-anchor at the current turn count and cost
```

## Edge Cases
- **Precedence**: If a CLI flag, an environment variable, a config value, and a default all exist, then the guard uses the CLI flag first, then the environment variable, then the config value, then the default, because operators expect the most specific setting to win.
- **Reset disabled**: If `guardrails.message_reset` is false, then both baselines stay fixed for the whole run, because the operator opted out of the reset.
- **Checkpoint reset**: If a message turn completes and `guardrails.message_reset` is true, then the guard re-anchors both baselines BEFORE the limit check, because the human is present and approves continuation. The message turn therefore never trips the limit.
- **Empty reply**: If a message turn yields an empty reply, then the session terminates before any reset, because the session ends.
- **Pipeline exit**: If a pipeline run stops after its first message turn, then the reset never applies, because the process exits before the next turn.
- **Turn limit rounding**: If the turn count lands exactly on the limit, then the guard stops the run, because the comparison is inclusive.

## Key Unknowns
- [x] [Domain] Rename migration: RESOLVED — the guard MUST fall back to the legacy `yolo_guardrails` key when `guardrails` is absent, so existing user configs keep working. Read `guardrails.X`; when that result is absent, read `yolo_guardrails.X` before the default.
- [x] [Technical] Baseline re-anchor seam: RESOLVED — add an additive `reset_baseline(turn_count, cumulative_cost)` operation to `ISessionLoopGuard`. The guard already owns `_initial_turn` and `_initial_cost`, so re-anchoring them is the smallest, most testable seam. The session loop calls it after a communication turn, BEFORE the limit check. No test fakes this port, so the extension has zero test blast radius.

## Impact
1. `[EXPAND]` `ISessionLoopGuard` port — add an additive `reset_baseline(turn_count, cumulative_cost)` operation. No test implements this port, so the extension has zero blast radius.
2. `[EXPAND]` `ProductionSessionLoopGuard` — read `guardrails.*` with a legacy `yolo_guardrails` fallback, implement `reset_baseline` gated by `guardrails.message_reset`, resolve the limit precedence, and raise the default turn limit to 150.
3. `[EXPAND]` `_orchestrate_session_loop` in `session_cli_handlers.py` — thread `--max-turns` and `--max-cost` into the guard and call `reset_baseline` after a communication turn, before the limit check.
4. `[MIGRATE]` Guard messages, bundled `config.yaml`, guard tests, and the `session_loop_guard.md` component doc — rename `yolo_guardrails` to `guardrails` and correct the component doc's stale config-missing defaults (it claims 10 turns / $1.00; the code uses 99 / $5.00, rising to 150). The README Environment Variables rows (`TEDDY_MAX_TURNS`, `TEDDY_MAX_SESSION_COST`) are already present; verify them.
5. `[CONTRACT]` The bundled `yolo_guardrails` block — remove after the rename. The code keeps the legacy fallback read for existing user configs.

## Deliverables
- [x] **Wiring** - Add `--max-turns` and `--max-cost` to `start` and `resume`, thread them to the loop guard, and honor them in the limit checks through a skeleton precedence read.
- [x] **Contract** - Extend `ISessionLoopGuard` with the additive `reset_baseline(turn_count, cumulative_cost)` operation.
- [x] **Logic** - Implement the precedence chain (CLI flag > env var > config value > default), the `TEDDY_MAX_TURNS` and `TEDDY_MAX_SESSION_COST` overrides, the legacy `yolo_guardrails` fallback read, the 150-turn default, and the message-turn reset gated by `guardrails.message_reset`.
- [ ] **Migration** - Rename `yolo_guardrails` to `guardrails` in the bundled config, the guard, the guard tests, and the `session_loop_guard.md` component doc. Correct the component doc's stale config-missing defaults.
- [ ] **Refactor** - Extract the limit resolution into a single helper.
- [ ] **Cleanup** - Remove the stale `--yolo`-only wording. Keep the legacy `yolo_guardrails` fallback read for existing user configs.

## Implementation Notes

### Wiring (delivered)

- Added shared Typer option constants `OPT_MAX_TURNS` and `OPT_MAX_COST` in `__main__.py`.
- Added `--max-turns` and `--max-cost` to both `start` and `resume`, and threaded them through `handle_new_session` and `handle_resume_session` into `_orchestrate_session_loop`.
- The loop passes both values as resolve kwargs to `ISessionLoopGuard`, so punq injects them into `ProductionSessionLoopGuard`.
- The guard constructor gained additive optional keywords `max_turns` and `max_cost`, both defaulting to `None`, so every existing caller stays valid.
- The limit read is a temporary skeleton precedence: an explicit CLI value wins, otherwise the guard falls back to the `yolo_guardrails` config value. The full chain (environment variable, legacy fallback, and the 150-turn default) arrives in the Logic deliverable.
- Acceptance proof: `tests/suites/acceptance/test_configurable_guardrails.py` drives `start -y --max-turns 1` and asserts the run stops at `1/1`.

### Contract (delivered)

- Added the additive `reset_baseline(self, turn_count, cumulative_cost) -> None` declaration to the `ISessionLoopGuard` Protocol.
- The port is a plain `Protocol` without `@runtime_checkable`, so both explicit subclasses (`ProductionSessionLoopGuard` and the harness's `TestSessionLoopGuard`) inherit the new method as an inert no-op stub. The extension therefore has zero blast radius.
- The concrete re-anchoring behavior, gated by `guardrails.message_reset`, arrives in the Logic deliverable. This deliverable only pins the port surface, so implementing behavior now would overbuild.
- Contract proof: `tests/suites/unit/core/ports/outbound/test_session_loop_guard_contract.py` pins the operation's presence and its exact `(self, turn_count, cumulative_cost)` signature.

### Logic (delivered)

- Added an `ISystemEnvironment` dependency and a `_read_config` helper to `ProductionSessionLoopGuard`. The helper reads `guardrails.<key>` and consults the legacy `yolo_guardrails.<key>` only when the renamed key is absent. A module-level `_UNSET` sentinel distinguishes "key absent" from a present falsy value.
- Added `_resolve_max_turns` and `_resolve_max_cost`. Each resolves through the precedence chain: the CLI flag first, then `TEDDY_MAX_TURNS`/`TEDDY_MAX_SESSION_COST`, then the config value, then the default. The turn default rose from 99 to 150; the cost default stays 5.0.
- Implemented `reset_baseline`, gated by `guardrails.message_reset` (default true), which re-anchors `_initial_turn` and `_initial_cost`.
- Wired the call site in `_orchestrate_session_loop`. After the cost is computed and BEFORE `should_continue`, a new `_is_communication_turn(report)` predicate detects a non-empty MESSAGE action and calls `loop_guard.reset_baseline(turn_count, cumulative_cost)`. The message turn therefore never trips the limit. The guard gates the actual re-anchor, so the call site stays unconditional after a communication turn.
- Logic proof: `tests/suites/unit/core/services/test_session_loop_guard_configuration.py` covers precedence, the environment overrides, the legacy fallback, the 150 default, the 5.0 default, the reset, and the disabled-reset case. `tests/suites/unit/adapters/inbound/test_session_loop_baseline_reset.py` covers the call site and its ordering before the limit check.
- Collateral repair: `_is_communication_turn` iterates `report.action_logs`, but `Mock(spec=ExecutionReport)` omits that `default_factory` field from the class namespace. Four `test_session_replan_loop.py` report doubles gained `action_logs = []`.
- Integration proof: `make test` reports `1833 passed, 5 skipped`.

### Harness constraint

- `TestEnvironment.setup()` registers `ISessionLoopGuard` as an instance mock that ignores resolve kwargs. The acceptance test therefore re-registers `ProductionSessionLoopGuard` as a class after setup, because the later class registration wins and receives the threaded kwargs.

### Debt

- The new acceptance test carries a minimal project-setup helper that mirrors `helpers.setup_project`. Consolidate it in the Refactor deliverable.

## Verification
- [ ] **Turn limit:**
    Run `teddy start -y --max-turns 1 -m "list the files"`.
    Verify the session stops after one turn with a limit message.
- [ ] **Environment override:**
    Run `TEDDY_MAX_TURNS=1 teddy start -y -m "list the files"`.
    Verify the session stops after one turn.
- [ ] **Message-turn reset:**
    Run a session with `guardrails.message_reset: true` and reply to a message turn.
    Verify the budget re-anchors after the reply.
