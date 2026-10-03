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
- [x] **Cleanup** - Remove the `--tui/--console` flag (`OPT_UI_MODE`), the two `apply_ui_mode_override` helpers ([src/teddy_executor/__main__.py](/src/teddy_executor/__main__.py) `_apply_ui_mode_override`; [src/teddy_executor/adapters/inbound/cli_helpers.py](/src/teddy_executor/adapters/inbound/cli_helpers.py) `apply_ui_mode_override`), and their `start`/`resume`/`execute` call sites; delete the console-mode acceptance test ([tests/suites/acceptance/test_ui_mode_toggling.py](/tests/suites/acceptance/test_ui_mode_toggling.py)) and drop `--console` from [tests/suites/acceptance/test_tui_instruction_bridge.py](/tests/suites/acceptance/test_tui_instruction_bridge.py) — green-to-green.
- [x] **Cleanup** - Collapse [src/teddy_executor/registries/reviewer.py](/src/teddy_executor/registries/reviewer.py) to TUI-only (drop the `ui_mode` parameter, the `IConfigService` lookup, and the console branch; keep the TUI factory as-is) and update [tests/suites/integration/core/services/test_reviewer_wiring.py](/tests/suites/integration/core/services/test_reviewer_wiring.py) (remove the console test + `ConsolePlanReviewer` import, collapse the two TUI tests into one `test_container_resolves_textual_reviewer`, drop the unused `yaml` import) — green-to-green.
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

**Deliverable 2 — Cleanup (`--tui/--console` flag + both `apply_ui_mode_override` helpers removal):**

- **Production removals (pure contraction):** ten surgical edits to [src/teddy_executor/__main__.py](/src/teddy_executor/__main__.py) — the `_apply_ui_mode_override` helper (and its inner `register_reviewer` import), the `OPT_UI_MODE` Typer option, the `ui_mode` parameter on `start`/`resume`/`execute`, the three `if ui_mode is not None:` call sites, and the two `apply_ui_mode_override` imports (`resume`'s direct import + `execute`'s `cli_helpers` import tuple) — plus one edit to [src/teddy_executor/adapters/inbound/cli_helpers.py](/src/teddy_executor/adapters/inbound/cli_helpers.py) deleting `apply_ui_mode_override`. The `Container` import was DELIBERATELY retained (still consumed by `create_failure_report`/`execute_valid_plan`/`handle_report_output`). The registry ([src/teddy_executor/registries/reviewer.py](/src/teddy_executor/registries/reviewer.py)) was DELIBERATELY left untouched — its console-vs-TUI branch is collapsed by Deliverable 3, so after this deliverable `register_reviewer` is invoked ONLY from `container.py` without `ui_mode` (default `"tui"` resolution) while `test_reviewer_wiring.py`'s console-config test still resolves `ConsolePlanReviewer` (deleted in Deliverable 4).
- **Coupled test edits (green-to-green):** deleted [tests/suites/acceptance/test_ui_mode_toggling.py](/tests/suites/acceptance/test_ui_mode_toggling.py) (it passed the now-removed `--console` flag and asserted the removed sequential `Approve? (y/n/m):` prompt). Dropped `--console` from [tests/suites/acceptance/test_tui_instruction_bridge.py](/tests/suites/acceptance/test_tui_instruction_bridge.py) and corrected the stale "We force `--console` mode because CliRunner cannot drive Textual TUI apps" comment — this edit is behaviorally neutral because that test wires `.with_real_interactor()` (→ `HarnessPlanReviewer`), so `--console=None` simply skips the override and the harness-registered reviewer is used.
- **Poka-Yoke removal pin:** [tests/suites/unit/adapters/inbound/test_cli_console_mode_removal.py](/tests/suites/unit/adapters/inbound/test_cli_console_mode_removal.py) (Unit layer) asserts the console-mode flag surface (`OPT_UI_MODE`, `_apply_ui_mode_override`, `cli_helpers.apply_ui_mode_override`) no longer exists, guarding against silent re-introduction once the Textual TUI is the sole reviewer. Anti-mock-poisoning: the test imports the real module surface — no doubles needed.
- **Red→Green→Refactor:** Red was a TRUE Red (`1 failed`, `AssertionError: assert not True` on `assert not hasattr(main_module, "OPT_UI_MODE")`), proving the test demanded the removal rather than asserting a self-satisfying condition. Green flipped the suite to `1 passed`. Refactor surfaced a single local `W292` trailing-newline finding on the new test file (file-scoped, semantics-free), auto-fixed via `ruff check --fix`; `ruff check` + `ruff format --check` then clean.
- **Integration & verification evidence:** full unfiltered suite green at `1463 passed, 5 skipped` (net-zero vs the Turn-10 baseline: +1 new removal-pin test, −1 deleted console-mode test). A removal-completeness grep (`git grep -e "OPT_UI_MODE" -e "apply_ui_mode_override" -- src tests`) returned `NO HITS (removal complete)`. The Mypy run surfaced only the 8 PROJECT.md-documented PRE-EXISTING errors in five files this deliverable did NOT touch (`action_executor.py`, `session_orchestrator.py`, `console_interactor_ask_loop.py`, `textual_plan_reviewer_editor.py`, `textual_plan_reviewer_app.py`) — zero attributable to the change set.
- **Deliberate non-refactors:** the `# noqa: PLR0913` directives on `start`/`resume`/`execute` are pre-existing and STILL required (each command remains far above the 5-argument threshold after one-parameter removal), so they were not stripped; no config/magic-number centralization or shadow-logic concerns arose (pure subtraction).

**Deliverable 3 — Cleanup (registry collapse to TUI-only + wiring-test update):**

- **Production collapse (pure contraction, non-breaking):** [src/teddy_executor/registries/reviewer.py](/src/teddy_executor/registries/reviewer.py) was reduced to a `register_reviewer(container)` that unconditionally registers the Textual TUI factory — dropping the `ui_mode` parameter, the `IConfigService` lookup, and the entire `if ui_mode == "console":` branch (plus its `ConsolePlanReviewer` import). The TUI factory body is byte-identical. The signature change is Green-to-Green because the ONLY remaining caller ([src/teddy_executor/container.py](/src/teddy_executor/container.py) — `register_reviewer(container)`) already omitted `ui_mode` after Deliverable 2.
- **Stale-config Edge-Case test (the Red):** the honest atomic failing test pins the ONE behavior the collapse changes — the slice's declared Edge Case "a stale `ui_mode: console` key in a user's `config.yaml` must be silently ignored". Delivered as `test_container_ignores_stale_console_config` in [tests/suites/integration/core/services/test_reviewer_wiring.py](/tests/suites/integration/core/services/test_reviewer_wiring.py) (composition-root wiring layer — it composes the REAL container over pyfakefs and reads only the resolved adapter type).
- **Coupled test edits:** removed the `ConsolePlanReviewer` import and the console-config test (`test_container_resolves_console_reviewer_when_configured`), and collapsed the two TUI tests (`_by_default` + `_when_configured`) into a single `test_container_resolves_textual_reviewer`. The `yaml` import was DELIBERATELY RETAINED (not dropped as the deliverable text assumed) because the new stale-config test uses `yaml.dump`.
- **Red→Green→Refactor:** Red was a TRUE Red (`1 failed, 3 passed` — `AssertionError: assert False + where False = isinstance(<ConsolePlanReviewer object at 0x...>, TextualPlanReviewer)`), proving the test demanded the collapse. Green flipped the suite to `2 passed`. Refactor fixed one residual in-scope literal — the docstring token `ui_mode` at `reviewer.py:9` (the last `ui_mode`/`ConsolePlanReviewer` reference in the registry) was reworded to "No configuration key can select an alternative reviewer", closing a removal-completeness grep to `NO ui_mode / ConsolePlanReviewer IN REGISTRY (collapse complete)`.
- **Integration evidence:** the full unfiltered suite closed green at `1462 passed, 5 skipped` (net −1 vs the Deliverable-2 baseline: −1 console test removed, −1 TUI test collapsed, +1 stale-config Edge-Case test). Mypy surfaced only the PROJECT.md-documented PRE-EXISTING errors in untouched files the registry's lazy TUI import reaches — zero attributable to the change set.
- **Deliberate non-touch:** the production `ConsolePlanReviewer` module still EXISTS after this deliverable (deleted in Deliverable 4); the registry simply stopped importing it, keeping the deletion ordering Green-to-Green.

## Verification
1. `uv run pytest tests/suites/integration/core/services/test_reviewer_wiring.py -v` passes.
2. `uv run pytest tests/suites/acceptance/test_tui_instruction_bridge.py -v` passes (message captured through the real interactor via the harness double).
3. `uv run pytest tests/suites/acceptance/test_change_preview_feature.py -v` passes (its `Approve? (y/n/m):` assertion still holds).
4. Full suite is green-to-green: `uv run pytest` (no new failures).
5. `uv run teddy start --help` and `uv run teddy execute --help` no longer list `--console` / `--tui` (TUI is the sole mode).
6. `src/teddy_executor/adapters/outbound/console_interactor_ask_loop.py` is unchanged, and `IUserInteractor.confirm_action` is still wired via `action_executor.py`.
7. `git grep -n -e "ConsolePlanReviewer" -e "console_plan_reviewer" -e "OPT_UI_MODE" -e "apply_ui_mode_override" -e "ui_mode" -- src tests` returns NO hits (historical references under `docs/project/debugging/` and `docs/project/milestones/` are acceptable).
