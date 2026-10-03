# Task: Deprecate `--console` Mode & Remove the Console Plan Reviewer

## Business Goal
Remove the deprecated `--console` CLI mode and its dead code paths so interactive plan review unconditionally uses the Textual TUI, while preserving the console ask-loop that still powers free-text Response prompting.

## Context
This task fulfills the Milestone 5 requirement **"Deprecate `--console` Mode: Remove the `--console` mode and all related dead code paths."** It is scoped precisely to the request:

- **REMOVE:** the `--tui/--console` CLI flag, its two `ui_mode` override helpers, the `registries/reviewer.py` console-vs-TUI branch, and the `ConsolePlanReviewer` adapter (`adapters/inbound/console_plan_reviewer.py`) — the sequential "Approve? (y/n/m):" plan reviewer.
- **PRESERVE (do NOT touch):** `adapters/outbound/console_interactor_ask_loop.py` and the `Response (type 'e' for editor) ›` prompt used during the initial request and for Message-action replies. The `IUserInteractor.confirm_action` primitive is still consumed by `action_executor.py:114` and MUST remain.

### Current behavior (removal surface)
- `src/teddy_executor/__main__.py` defines `OPT_UI_MODE` (`--tui/--console`) and applies it via `_apply_ui_mode_override` (`start`) and `apply_ui_mode_override` (`resume`, `execute`).
- `src/teddy_executor/adapters/inbound/cli_helpers.py` holds the duplicate `apply_ui_mode_override`.
- `src/teddy_executor/registries/reviewer.py` reads `ui_mode` (default `"tui"`) and registers either `ConsolePlanReviewer` (console) or the Textual TUI factory. `config.yaml` carries **no** `ui_mode` key — the `"tui"` default is hard-coded at the call site.
- After removal, TUI is the only reviewer, so `--tui` is redundant and is removed alongside `--console`.

### Test-harness coupling (the non-trivial part)
`tests/harness/setup/real_adapter_mixin.py::with_real_interactor()` currently registers the **production** `ConsolePlanReviewer`, because `CliRunner` cannot drive the Textual TUI. Roughly 30 acceptance tests call `.with_real_interactor()` and rely on the sequential reviewer driving the real `ConsoleInteractorAdapter` (diff preview + `Approve? (y/n/m):` prompt + stdin consumption). Deleting the production adapter therefore **requires** a replacement.

**Approved strategy:** relocate a thin reviewer double into `tests/harness/setup/` that mirrors the removed class verbatim and delegates to the real `ConsoleInteractorAdapter.confirm_action`. This preserves the diff-preview/prompt/stdin path the acceptance tests exercise. (Driving the TUI directly is rejected: it is structurally impossible inside `CliRunner`, materially slower, and redundant with the dedicated `test_tui_*` / `test_reviewer_app_*` suites.)

### Out of scope
- `IUserInteractor.confirm_plan_review` appears uncalled in production today (only its implementation and one unit test reference it). Removing it is a PORT change, not a dead-code-only cleanup, so it is deferred. Log it as a follow-up if confirmed dead.
- Any change to the ask-loop, `ConsoleInteractorAdapter.confirm_action`, or the editor-`e` path.

## Implementation Steps

### Step 1: Remove the flag, the override helper, and its call sites in `__main__.py`
- **File:** [src/teddy_executor/__main__.py](/src/teddy_executor/__main__.py)
- **Change:**
  1. Delete the `OPT_UI_MODE` definition (`None, "--tui/--console", help="Force TUI or Console mode.", show_default=False`).
  2. Delete the `_apply_ui_mode_override(container, ui_mode_bool)` function (and its inner `register_reviewer` import).
  3. In `start`, `resume`, and `execute`: remove the `ui_mode: Optional[bool] = OPT_UI_MODE,` parameter.
  4. In `start`: remove the `if ui_mode is not None: _apply_ui_mode_override(container, ui_mode)` block.
  5. In `resume`: remove the `from teddy_executor.adapters.inbound.cli_helpers import apply_ui_mode_override` line and the `if ui_mode is not None: apply_ui_mode_override(container, ui_mode)` block.
  6. In `execute`: remove `apply_ui_mode_override,` from the `cli_helpers` import tuple and the `if ui_mode is not None: apply_ui_mode_override(container, ui_mode)` block.

### Step 2: Remove `apply_ui_mode_override` from `cli_helpers.py`
- **File:** [src/teddy_executor/adapters/inbound/cli_helpers.py](/src/teddy_executor/adapters/inbound/cli_helpers.py)
- **Change:** Delete the `apply_ui_mode_override` function. Confirm no other symbol in the file becomes unused (e.g., an orphaned `Container` import) and clean up if so.

### Step 3: Collapse `registries/reviewer.py` to TUI-only
- **File:** [src/teddy_executor/registries/reviewer.py](/src/teddy_executor/registries/reviewer.py)
- **Change:** Replace the module body with a `register_reviewer(container)` that unconditionally registers the Textual TUI factory:
  - Signature becomes `def register_reviewer(container: punq.Container) -> None:` (drop the `ui_mode` parameter).
  - Remove the `IConfigService` lookup and the entire `if ui_mode == "console":` branch (and its `ConsolePlanReviewer` import).
  - Keep the TUI factory exactly as-is (its lazy `TextualPlanReviewer` import stays).

### Step 4: Delete the console plan reviewer adapter
- **File:** [src/teddy_executor/adapters/inbound/console_plan_reviewer.py](/src/teddy_executor/adapters/inbound/console_plan_reviewer.py)
- **Change:** Delete the file (use `git rm`). No contract doc exists for it, so no doc deletion is required.

### Step 5: Create the harness reviewer double
- **File:** [tests/harness/setup/harness_plan_reviewer.py](/tests/harness/setup/harness_plan_reviewer.py)
- **Change:** Create `HarnessPlanReviewer(IPlanReviewer)` mirroring the deleted `ConsolePlanReviewer` verbatim: the same constructor deps (`user_interactor`, `file_system_manager`, `config_service`, `edit_simulator`) building an `ActionChangeSetBuilder`; a `review()` that prints the `▶ Reviewing Plan:` header via `typer.secho(..., err=True)` and returns the plan; a `review_action()` that formats the action prompt, builds the change set, calls `self._user_interactor.confirm_action(action=..., action_prompt=..., change_set=...)`, sets `action.selected`, and returns `(approved, message)`.

### Step 6: Point the harness at the double
- **File:** [tests/harness/setup/real_adapter_mixin.py](/tests/harness/setup/real_adapter_mixin.py)
- **Change:** In `with_real_interactor()`, replace the `ConsolePlanReviewer` import + `self._container.register(IPlanReviewer, ConsolePlanReviewer)` with `from tests.harness.setup.harness_plan_reviewer import HarnessPlanReviewer` and `self._container.register(IPlanReviewer, HarnessPlanReviewer)`. Leave the `IUserInteractor → ConsoleInteractorAdapter` registration untouched.

### Step 7: Update the reviewer-wiring integration test
- **File:** [tests/suites/integration/core/services/test_reviewer_wiring.py](/tests/suites/integration/core/services/test_reviewer_wiring.py)
- **Change:** Remove the `ConsolePlanReviewer` import and `test_container_resolves_console_reviewer_when_configured`. Collapse the two remaining TUI tests into a single `test_container_resolves_textual_reviewer` (default config → `TextualPlanReviewer`) and drop the now-unused `yaml` import.

### Step 8: Delete the console-mode acceptance test
- **File:** [tests/suites/acceptance/test_ui_mode_toggling.py](/tests/suites/acceptance/test_ui_mode_toggling.py)
- **Change:** Delete the file (`git rm`) — it passes `--console` and asserts the removed console prompt.

### Step 9: Delete the production reviewer unit test
- **File:** [tests/suites/unit/adapters/inbound/test_console_plan_reviewer.py](/tests/suites/unit/adapters/inbound/test_console_plan_reviewer.py)
- **Change:** Delete the file (`git rm`) — it tests the deleted class. The double's behavior is covered end-to-end by the acceptance suite through `with_real_interactor()`.

### Step 10: Drop `--console` from the instruction-bridge acceptance test
- **File:** [tests/suites/acceptance/test_tui_instruction_bridge.py](/tests/suites/acceptance/test_tui_instruction_bridge.py)
- **Change:** In `test_tui_instruction_bridge_m_binding_captures_message`, remove `"--console"` from the `adapter.run_cli_command([...])` args (the harness double now handles review). Update the stale "We force `--console` mode because CliRunner cannot drive Textual TUI apps" comment.

### Step 11: Remove the `ui_mode` special-case from the harness config mock
- **File:** [tests/harness/setup/test_environment.py](/tests/harness/setup/test_environment.py)
- **Change:** In `_apply_config_defaults`, replace `mock.get_setting.side_effect = lambda k, d=None: None if k == "ui_mode" else d` with `mock.get_setting.side_effect = lambda k, d=None: d`.

### Step 12: Rename the `ui_mode` config-adapter tests
- **File:** [tests/suites/unit/adapters/outbound/test_yaml_config_adapter.py](/tests/suites/unit/adapters/outbound/test_yaml_config_adapter.py)
- **Change:** Rename `test_get_setting_retrieves_ui_mode` and `test_get_setting_ui_mode_defaults_to_tui_at_call_site` to neutral names and swap the `"ui_mode"` key for a neutral example key, preserving the generic `get_setting` coverage.

### Step 13: Remove the dead `ui_mode` config key from the UI acceptance test
- **File:** [tests/suites/acceptance/test_context_management_ui.py](/tests/suites/acceptance/test_context_management_ui.py)
- **Change:** Remove the `"ui_mode": "tui",` entry from the config dict (~line 216).

### Step 14: Update the doc example
- **File:** [docs/project/specs/openrouter-monetization-oauth.md](/docs/project/specs/openrouter-monetization-oauth.md)
- **Change:** Remove `ui_mode` from the example config-key list (~line 29), keeping e.g. `editor`, `auto_pruning`.

### Step 15: Audit `test_change_preview_feature.py`
- **File:** [tests/suites/acceptance/test_change_preview_feature.py](/tests/suites/acceptance/test_change_preview_feature.py)
- **Change:** This test asserts on the real `Approve? (y/n/m):` prompt (line 62) but does NOT call `with_real_interactor()` and does NOT reference `ConsolePlanReviewer` (per grep). Audit how it wires `IUserInteractor`/`IPlanReviewer`. If it depends on the deleted `ConsolePlanReviewer`, retarget it to the harness double (e.g., add `.with_real_interactor()`); otherwise, no change.

## Verification
1. `git grep -n -e "ConsolePlanReviewer" -e "console_plan_reviewer" -e "OPT_UI_MODE" -e "apply_ui_mode_override" -e "ui_mode" -- src tests` returns NO hits (historical references under `docs/project/debugging/` and `docs/project/milestones/` are acceptable).
2. `git grep -n -e '"--console"' -e '"--tui"' -- src tests` returns NO hits.
3. `uv run pytest tests/suites/integration/core/services/test_reviewer_wiring.py -v` passes.
4. `uv run pytest tests/suites/acceptance/test_tui_instruction_bridge.py -v` passes (message captured through the real interactor via the harness double).
5. `uv run pytest tests/suites/acceptance/test_change_preview_feature.py -v` passes (its `Approve? (y/n/m):` assertion still holds).
6. Full suite is green-to-green: `uv run pytest` (no new failures).
7. `uv run teddy start --help` and `uv run teddy execute --help` no longer list `--console` / `--tui` (TUI is the sole mode).
8. `src/teddy_executor/adapters/outbound/console_interactor_ask_loop.py` is unchanged, and `IUserInteractor.confirm_action` is still wired via `action_executor.py`.
