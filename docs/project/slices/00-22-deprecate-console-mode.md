# Slice: Deprecate `--console` Mode & Remove the Console Plan Reviewer
- **Status:** In Progress
- **Milestone:** [Milestone 5](/docs/project/milestones/05-quality-gate-debt-reconciliation.md)
- **Specs:** [Task Brief](/docs/project/tasks/deprecate-console-mode.md)
- **Prototype:** [N/A — no spike required; removal surface fully mapped during Orientation]
- **Component Docs:** [CLI Adapter](/docs/architecture/adapters/inbound/cli.md), [IPlanReviewer](/docs/architecture/core/ports/inbound/plan_reviewer.md)
- **Scope Slug:** `deprecate-console-mode`

## Business Goal
Remove the deprecated `--console` CLI mode and its dead code paths so that interactive plan review unconditionally uses the Textual TUI, while preserving the console ask-loop that still powers free-text Response prompting.

## Scenarios

> As a user reviewing a plan, I want the Textual TUI to always be the plan reviewer so that there is a single, consistent review experience.

```gherkin
Given a project with no ui_mode configuration
When I run teddy execute on a plan interactively
Then the plan review uses the Textual TUI reviewer
And no console ("Approve? (y/n/m):") sequential review path is selected
```

> As a user, I want the deprecated --console/--tui flags removed so that the CLI surface is unambiguous.

```gherkin
Given the CLI help output for "teddy start" and "teddy execute"
When I inspect the available options
Then neither --console nor --tui is listed
```

> As a user answering a Message-action reply prompt, I want the console ask-loop preserved so that free-text replies still work.

```gherkin
Given an interactive session
When the agent emits a Message and awaits a reply
Then the console "Response (type 'e' for editor) ›" prompt is still available
And the reply is captured as before
```

## Edge Cases
- **Harness reviewer parity**: If an acceptance test needs a plan reviewer under CliRunner (which cannot drive Textual), then the harness must provide a double mirroring the removed console reviewer, in order to keep the diff-preview/prompt/stdin path exercised.
- **Config-free mode resolution**: If no `ui_mode` config key exists, then the registry resolves to the Textual TUI unconditionally, in order to make TUI the sole mode.
- **Stale `ui_mode` config**: If a user's `config.yaml` still contains a `ui_mode` key, then it is silently ignored, because the console-selection branch no longer exists in order to avoid breaking existing configs.
- **Ask-loop preservation**: If a Message-action reply prompt is triggered, then the console ask-loop path is untouched, in order to preserve free-text replies.

## Key Unknowns
- [x] [Technical] Does `test_change_preview_feature.py` depend on the deleted `ConsolePlanReviewer`? — Resolved: No; it uses `without_reviewer()` (IPlanReviewer=None) and asserts the real interactor's `confirm_action` diff-preview prompt. No change required.
- [x] [Technical] Is dropping the `ui_mode` parameter of `register_reviewer` a breaking change? — Resolved: No; its only remaining caller (`container.py`) already omits it, and the two `ui_mode` call sites are removed by the flag-removal deliverable.
- [x] [Technical] Can the Textual TUI be driven for the acceptance gate? — Resolved: No (structural inside CliRunner). The harness double (delegating to the real `ConsoleInteractorAdapter.confirm_action`) keeps the behavioral path exercised; the TUI itself is covered by the dedicated `test_tui_*` / `test_reviewer_app_*` suites.

## Implementation Plan
This is a removal/contraction slice fulfilling the Milestone 5 requirement "Deprecate `--console` Mode." The work is ordered to keep every step a Green-to-Green transition despite a Shared-Seam signature change (`register_reviewer`):

1. Relocate the harness reviewer double FIRST (`Harness`) so the ~30 CliRunner acceptance tests that call `with_real_interactor()` remain exercised before the production adapter is touched. The double (`HarnessPlanReviewer`) mirrors the removed `ConsolePlanReviewer` verbatim and delegates to the real `ConsoleInteractorAdapter.confirm_action`, preserving the diff-preview / `Approve? (y/n/m):` / stdin path that CliRunner exercises (the Textual TUI is structurally undrivable inside CliRunner).
2. Remove the `--tui/--console` flag, `OPT_UI_MODE`, both `apply_ui_mode_override` helpers, and their call sites (`Cleanup`), bundling the coupled test edits (delete `test_ui_mode_toggling.py`; drop `--console` from `test_tui_instruction_bridge.py`). After this, `register_reviewer` is only invoked from the composition root without `ui_mode`, so the registry's config lookup resolves the `"tui"` default.
3. Collapse the registry to TUI-only (`Cleanup`) — dropping the now-unsafe-if-kept `ui_mode` parameter, the `IConfigService` lookup, and the console branch — and bundle the `test_reviewer_wiring.py` update (the console-config test would otherwise fail).
4. Delete the production `ConsolePlanReviewer` adapter and its unit test (`Cleanup`) once no importer remains.
5. Sweep the residual `ui_mode` references in the harness/docs (`Cleanup`).
6. Final behavioral gate (`Wiring`): pin the absence of `--console`/`--tui` in the CLI help and an end-to-end flag-free plan-review run.

Test strategy: the harness double's contract is pinned by a Unit test (conformance + delegation to `confirm_action`); the removal is verified by the existing acceptance suite (unchanged behavior through the double) plus the final Wiring acceptance gate. Anti-mock-poisoning: the double is a hand-rolled class implementing `IPlanReviewer` (no bare `MagicMock`).

Green-to-green ordering rationale: the `register_reviewer` signature change (Step 3) is non-breaking because the only caller after Step 2 passes no `ui_mode`; the production adapter deletion (Step 4) is only safe after Step 1 (harness repoint) and Step 3 (registry import removal).

## Deliverables
- [x] **Harness** - Create `HarnessPlanReviewer` ([tests/harness/setup/harness_plan_reviewer.py](/tests/harness/setup/harness_plan_reviewer.py)) — a verbatim mirror of the removed `ConsolePlanReviewer` (same constructor deps building an `ActionChangeSetBuilder`; `review()` prints the `▶ Reviewing Plan:` header and returns the plan; `review_action()` delegates to `IUserInteractor.confirm_action` and sets `action.selected`) — and repoint `with_real_interactor()` in [tests/harness/setup/real_adapter_mixin.py](/tests/harness/setup/real_adapter_mixin.py) to register it — unit test pinning `IPlanReviewer` conformance and delegation.
- [ ] **Cleanup** - Remove the `--tui/--console` flag (`OPT_UI_MODE`), the two `apply_ui_mode_override` helpers ([src/teddy_executor/__main__.py](/src/teddy_executor/__main__.py) `_apply_ui_mode_override`; [src/teddy_executor/adapters/inbound/cli_helpers.py](/src/teddy_executor/adapters/inbound/cli_helpers.py) `apply_ui_mode_override`), and their `start`/`resume`/`execute` call sites; delete the console-mode acceptance test ([tests/suites/acceptance/test_ui_mode_toggling.py](/tests/suites/acceptance/test_ui_mode_toggling.py)) and drop `--console` from [tests/suites/acceptance/test_tui_instruction_bridge.py](/tests/suites/acceptance/test_tui_instruction_bridge.py) — green-to-green.
- [ ] **Cleanup** - Collapse [src/teddy_executor/registries/reviewer.py](/src/teddy_executor/registries/reviewer.py) to TUI-only (drop the `ui_mode` parameter, the `IConfigService` lookup, and the console branch; keep the TUI factory as-is) and update [tests/suites/integration/core/services/test_reviewer_wiring.py](/tests/suites/integration/core/services/test_reviewer_wiring.py) (remove the console test + `ConsolePlanReviewer` import, collapse the two TUI tests into one `test_container_resolves_textual_reviewer`, drop the unused `yaml` import) — green-to-green.
- [ ] **Cleanup** - Delete the production `ConsolePlanReviewer` adapter ([src/teddy_executor/adapters/inbound/console_plan_reviewer.py](/src/teddy_executor/adapters/inbound/console_plan_reviewer.py)) and its unit test ([tests/suites/unit/adapters/inbound/test_console_plan_reviewer.py](/tests/suites/unit/adapters/inbound/test_console_plan_reviewer.py)) — green-to-green (no importer remains after the two preceding deliverables).
- [ ] **Cleanup** - Remove the residual `ui_mode` references: the harness config-mock special-case ([tests/harness/setup/test_environment.py](/tests/harness/setup/test_environment.py) → `lambda k, d=None: d`), rename + neutralize the two `get_setting` tests ([tests/suites/unit/adapters/outbound/test_yaml_config_adapter.py](/tests/suites/unit/adapters/outbound/test_yaml_config_adapter.py)), drop the dead config key ([tests/suites/acceptance/test_context_management_ui.py](/tests/suites/acceptance/test_context_management_ui.py)), and update the doc example ([docs/project/specs/openrouter-monetization-oauth.md](/docs/project/specs/openrouter-monetization-oauth.md)) — green-to-green.
- [ ] **Wiring** - Final behavioral gate: acceptance test asserting `--console`/`--tui` are absent from `teddy start --help` / `teddy execute --help` and that an interactive plan-review run proceeds end-to-end without any console flag (via the harness reviewer), covering the Gherkin scenarios.

## Implementation Notes

**Deliverable 1 — Harness (`HarnessPlanReviewer` relocation):**

- **Verbatim relocation (zero business logic):** [tests/harness/setup/harness_plan_reviewer.py](/tests/harness/setup/harness_plan_reviewer.py) is a behavioral mirror of the production `ConsolePlanReviewer` — same four Constructor-Injected deps (`user_interactor`, `file_system_manager`, `config_service`, `edit_simulator`) building an `ActionChangeSetBuilder`; `review()` prints the `▶ Reviewing Plan:` header via `typer.secho(..., err=True)` and returns the plan untouched (no bulk summary); `review_action()` formats the prompt via the imported `ActionChangeSetBuilder.format_action_prompt` (the source of truth — no shadow logic), builds the change set, delegates to `IUserInteractor.confirm_action(action=..., action_prompt=..., change_set=...)`, sets `action.selected`, and returns `(approved, message)`. The deliberate verbatim copy guarantees the ~30 CliRunner acceptance tests see identical behavior through the double; it creates no lasting duplication because the production class is deleted in Deliverable 4.
- **Harness repoint:** `with_real_interactor()` ([tests/harness/setup/real_adapter_mixin.py](/tests/harness/setup/real_adapter_mixin.py)) now imports `HarnessPlanReviewer` from `tests.harness.setup.harness_plan_reviewer` and registers it as `IPlanReviewer`, leaving the `IUserInteractor → ConsoleInteractorAdapter` registration byte-identical. This keeps the diff-preview / `Approve? (y/n/m):` / stdin path exercised under `CliRunner` (the Textual TUI is structurally undrivable inside `CliRunner`).
- **Test layer & anti-mock-poisoning:** the contract test lives in the Unit layer ([tests/suites/unit/test_harness_plan_reviewer.py](/tests/suites/unit/test_harness_plan_reviewer.py)) because the double imports the internal `IPlanReviewer` core port (banned from Acceptance by the test-layer-isolation rule). Port doubles are strictly spec-bound `Mock(spec=...)` (no bare `MagicMock`, no global `patch`). The suite pins four edges: `IPlanReviewer` runtime-checkable conformance; `review()` returns the plan without invoking `confirm_action`; `review_action()` delegates with a formatted prompt + a `ChangeSet` and returns the interactor tuple with `action.selected` set; denial sets `action.selected is False`.
- **Red→Green→Refactor:** Red was a TRUE Red (collection-time `ModuleNotFoundError: No module named 'tests.harness.setup.harness_plan_reviewer'`, 1 error). Green flipped the suite to `4 passed`. Refactor surfaced only two `W292` trailing-newline findings on the two new files (local, file-scoped), auto-fixed via `ruff check --fix`; `ruff check` + `ruff format --check` then clean. Integration gate: full unfiltered suite green at `1463 passed, 5 skipped`, proving the repoint is behavior-preserving.
- **Deliberate non-refactors:** the module-level `ActionChangeSetBuilder` import placement (after the `TYPE_CHECKING` block) is preserved verbatim for behavior parity; no shared-helper extraction was warranted here.

**Open thread (harvested to PROJECT.md):** `IUserInteractor.confirm_plan_review` has no production call site; its removal is explicitly deferred by the Task Brief (a Port change, not dead-code-only cleanup).

## Verification
1. `uv run pytest tests/suites/integration/core/services/test_reviewer_wiring.py -v` passes.
2. `uv run pytest tests/suites/acceptance/test_tui_instruction_bridge.py -v` passes (message captured through the real interactor via the harness double).
3. `uv run pytest tests/suites/acceptance/test_change_preview_feature.py -v` passes (its `Approve? (y/n/m):` assertion still holds).
4. Full suite is green-to-green: `uv run pytest` (no new failures).
5. `uv run teddy start --help` and `uv run teddy execute --help` no longer list `--console` / `--tui` (TUI is the sole mode).
6. `src/teddy_executor/adapters/outbound/console_interactor_ask_loop.py` is unchanged, and `IUserInteractor.confirm_action` is still wired via `action_executor.py`.
7. `git grep -n -e "ConsolePlanReviewer" -e "console_plan_reviewer" -e "OPT_UI_MODE" -e "apply_ui_mode_override" -e "ui_mode" -- src tests` returns NO hits (historical references under `docs/project/debugging/` and `docs/project/milestones/` are acceptable).
