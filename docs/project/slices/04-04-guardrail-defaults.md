# Slice: Guardrail Budget Verification and Regression Pins
- **Status:** In Progress
- **Milestone:** [Milestone 4: TUI & UX Enhancements](/docs/project/milestones/04-tui-ux-enhancements.md)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [ConfigSchema](/docs/architecture/core/domain/config_schema.md), [SessionLoopGuard](/docs/architecture/core/services/session_loop_guard.md), [ISessionLoopGuard](/docs/architecture/core/ports/outbound/session_loop_guard.md)
- **Scope Slug:** `guardrail-budget-pins`

## Goal
Guarantee that an unattended run is bounded by 150 turns and $5.00 counted from zero on every resume, by correcting the resumed turn baseline and pinning the result, so neither a future refactor nor a stale literal can silently restore a cumulative budget or make the limits bite an interactive run.

## Context
- The behaviour is delivered, and this slice adds no production code. `--max-turns` and `--max-cost` exist on both `start` and `resume` (`__main__.py:225`, `:268-269`, `:572-573`), so no flag has to be introduced.
- **Yolo-only:** `should_continue` returns `(True, None)` when `require_approval` is set (`session_loop_guard.py:76-77`) and again when `guardrails.enabled` is false (`:79-80`), so an interactive run never trips either limit and an operator can opt out entirely.
- **Precedence:** `_resolve_limit` walks explicit override, then `TEDDY_MAX_TURNS` / `TEDDY_MAX_SESSION_COST`, then `guardrails.<key>`, then the default. The cost default is `5.0` (`:62-71`); the turn default is `150` (`:54-60`).
- **Non-cumulative across resume:** `_orchestrate_session_loop` seeds `initial_turn` and `initial_cost` from the session's persisted totals before constructing the guard (`session_cli_handlers.py:585-596`), so a resumed run's deltas start at zero rather than at the session's lifetime totals. `reset_baseline` (`:110-119`) re-anchors both after a message turn while `guardrails.message_reset` is true.
- **Four spellings of 150 already agree:** `config_schema.py:86`, bundled `config.yaml:42`, the `_resolve_max_turns` fallback at `session_loop_guard.py:58`, and the guard page's Data Contracts. `max_session_cost` agrees at `5.0` in the schema and `5.00` in the bundled YAML.
- **Existing coverage:** `test_session_loop_guard.py`, `test_session_loop_guard_configuration.py`, `test_session_loop_baseline_reset.py`, `test_pipeline_wiring.py` and the port contract `test_session_loop_guard_contract.py` already exercise the chain. What is not measured is whether the resume seed and the yolo-only gate each have a named pin.
- **Product decision (2026-11-26):** the default stays `150`. The `99` this slice previously carried is withdrawn, and no spelling changes.
- **Out of scope:** the money format. [04-05](./04-05-context-metadata.md) owns `format_cost_usd` and the four-decimal standard, which is what replaces the halt notice's local `:.2f`; duplicating it here would give the notice two owners.
- **Why a pin instead of nothing:** the resume seed is one constructor argument away from reverting to a cumulative budget, and that regression is silent — the run simply stops early. A behavioural guarantee that nothing asserts is a guarantee that lasts until the next refactor of the same call site.
- **Discovery result:** the yolo-only gate is already pinned by `test_production_guard_ignores_limits_in_interactive_mode`; the resume seed is not pinned behaviourally, and the behaviour it would have asserted is wrong.
- **The defect:** `_orchestrate_session_loop` seeds the guard with `initial_turn = _resolve_initial_turn(...)`, which returns `max(0, latest_turn - 1)` parsed from the session's latest turn directory, while the loop itself passes a per-run counter that restarts at `1`. A session whose latest turn is `40` therefore seeds `39`, the first `should_continue(1, ...)` computes `turn_delta = -38`, and the run halts at 189 turns instead of 150. The turn budget silently grows with the turns already spent — the cumulative-budget regression this slice exists to prevent, inverted.
- **The cost side is correct and stays untouched:** `SessionService.get_cumulative_cost` reads the session's `cumulative_cost`, and the loop passes the report's own `cumulative_cost`, so `cost_delta` genuinely starts at zero on resume.
- **Why the existing coverage missed it:** `test_session_loop_baseline_reset.py` injects a pre-built guard through `ContainerStub`, whose `resolve` discards constructor kwargs, so the seeded baseline is unobservable at the boundary; `test_production_guard_stores_initial_state` asserts `_initial_turn`/`_initial_cost` and would pass even if `should_continue` ignored both.
- **Fresh sessions are unaffected:** `create_session` seeds turn `01` before the loop starts, so the resolved baseline is already `0` and the delta already starts at `1`; dropping the resume seed changes nothing for `teddy start`.
- **The four 150 spellings:** the `GuardrailsConfig.max_turns` default, the bundled `config.yaml` value, the `_resolve_max_turns` fallback, and this page's Data Contracts. Each is pinned today to an independent literal, and nothing links them.
- **Corrected deliverable target:** `test_bundled_config_tree_limits.py` asserts only the context tree caps. The guardrail spellings belong with `test_session_loop_guard_configuration.py`, which already loads the bundled file through `tests/harness/setup/bundled_config.py`.

## Scenarios

> As an operator running yolo, I want the turn budget to stop the run where the documentation says it stops.

```gherkin
Given no CLI override, no environment variable, and no guardrails value in config
When a yolo run reaches 150 turns in this run
Then the guard halts with the turn-limit notice naming guardrails.max_turns
```

> As an operator resuming a long session, I want this run's budget to start from zero.

```gherkin
Given a session whose earlier turns already consumed 40 turns and 2.00 USD
When I resume with -y and no overrides
Then the first turn of this run counts as turn 1 and the run's cost delta starts at zero
And the guard halts at 150 turns in this run rather than at 189
```

> As an operator, I want an explicit flag to beat every configured value.

```gherkin
Given guardrails.max_turns is 150 and I pass --max-turns 5
When the run reaches 5 turns in this run
Then the guard halts with the turn-limit notice
```

> As a reviewer, I want the limits to stay out of my way.

```gherkin
Given a plan awaiting my approval on turn 200 of a session
When the loop asks the guard whether to continue
Then the guard continues without a limit notice
```

## Edge Cases
- **Explicit zero override**: If `--max-turns 0` is passed, then the guard halts before the first turn, because `0` is a deliberate operator choice and only `None` means absent.
- **Empty environment variable**: If `TEDDY_MAX_TURNS` is exported but empty, then resolution falls through to config, because an empty export must not be read as zero.
- **Configured zero**: If `guardrails.max_turns` is explicitly `0`, then the default is restored, because an accidental zero would halt every unattended run instantly.
- **Message reset disabled**: If `guardrails.message_reset` is false, then the baseline stays fixed for the whole run, because one budget must cover a long unattended conversation.
- **Guardrails disabled**: If `guardrails.enabled` is false, then both limits are ignored entirely, because the operator opted out of unattended bounds.
- **Spelling drift**: If any of the four 150 spellings changes alone, then the bundled-config assertion fails naming the disagreement, because a divergent copy silently restores an undocumented budget.
- **Cost formatting**: If the halt reason renders a cost, then it goes through `format_cost_usd` at four decimals, because [04-05](./04-05-context-metadata.md) owns that renderer and this slice must not fork it.
- **Baseline scale asymmetry**: If a run is resumed, then the turn budget counts per run (a per-run counter against a zero turn baseline) and the cost budget counts per run (a session-cumulative cost against a session-cumulative baseline), because both must measure this run while their raw inputs start at different origins.

## Key Unknowns
- [x] [Harness] Whether the resume-seeded baseline and the yolo-only gate each already have a named unit test. **Resolved:** the yolo-only gate is pinned by `test_production_guard_ignores_limits_in_interactive_mode`; the resume seed is unpinned *and* the behaviour it would have asserted is wrong. The slice therefore prepends a production fix and places the pin after it, because a pin written first would freeze the defect. The baselines are observable once `ContainerStub` records the kwargs of each `resolve` call, which is additive for every existing caller.

## Impact
1. `[EXTEND]` `tests/harness/setup/container_stub.py` — record the constructor kwargs of each `resolve` call, so a test can observe the baselines the boundary seeds. Additive: the current double discards kwargs, and no caller relies on that.
2. `[MIGRATE]` `src/teddy_executor/adapters/inbound/session_cli_handlers.py` — seed the turn baseline at `0` (the per-run scale the loop counts in) and delete the now-dead `_resolve_initial_turn` helper, keeping `initial_cost` seeded from `get_cumulative_cost`.
3. `[MIGRATE]` `tests/suites/unit/adapters/inbound/test_session_loop_baseline_reset.py` — add the resumed-run turn-budget pin: a session whose latest turn is `40` must still halt at `guardrails.max_turns` turns in this run.
4. `[MIGRATE]` `tests/suites/unit/core/services/test_session_loop_guard_configuration.py` — replace the local `_load_bundled_config` with the shared harness loader, and assert the bundled `guardrails.max_turns` and `guardrails.max_session_cost` equal the `GuardrailsConfig` defaults and the guard's resolution fallbacks.
5. `[PRUNE]` `tests/suites/unit/core/services/test_session_loop_guard.py::test_production_guard_stores_initial_state` — the private-attribute assertion is superseded by behavioural delta pins and would survive a regression in `should_continue`.

## Deliverables
- [▶] **Harness** — Record the resolve kwargs in `ContainerStub` (with its own unit test) so the boundary seed is observable, and pin the four guardrail spellings to the schema defaults and the guard's resolution fallbacks.
- [ ] **Core** — Re-base the turn budget per run: seed `initial_turn=0`, delete the dead `_resolve_initial_turn` helper, and pin the resumed-run budget with a boundary test.
- [ ] **Cleanup** — Retire the private-attribute guard test, consolidate the duplicated bundled-config loader, and record the delivered behaviour as built on the guard service and port pages.

## Implementation Notes

## Verification
1. **Configured halt:**
   Set `guardrails.max_turns: 2` in `.teddy/config.yaml` and run `uv run teddy start -y -m "explore the repo"`.
   Verify the run halts after two turns and the notice names `guardrails.max_turns`.
2. **Bundled default:**
   Run `uv run teddy init config` in a scratch directory.
   Verify `grep -A4 '^guardrails:' .teddy/config.yaml` prints `max_turns: 150`.
3. **Resume baseline:**
   Resume an existing session with `uv run teddy resume -y` and watch the turn counter.
   Verify the first turn of this run is reported as turn 1, not as the session's cumulative count.
4. **Interactive exemption:**
   Start a session without `-y` and keep approving plans past the configured turn limit.
   Verify no limit notice appears.
