# Task: Refine CLI Preflight Notifications and Retire the `teddy plan` Vestige

## Business Goal

Make the CLI's preflight notifications accurate, independently controllable and self-describing (including a discoverable way to silence them), and remove the dead code and stale documentation left behind when the `teddy plan` command was retired.

## Context

**Workstream A — notification refinement.** The preflight today emits ONE combined line, `ℹ Prompt/template drift detected. To restore the bundled defaults, run: teddy init prompts and teddy init templates`, gated by a single `checks.prompts_templates` config toggle. It conflates two independent concerns (prompts vs templates), uses vague "restore the bundled defaults" wording, and gives the user no pointer to how to turn the notification off. The agreed requirements are: (1) ONE count-aware yellow line per channel (prompts / templates), distinguishing CHANGED from MISSING files; (2) independent config toggles `checks.prompts` + `checks.templates` (keeping `checks.update`), with the old combined `checks.prompts_templates` key REMOVED outright — the feature is unreleased, so no backward-compatibility fallback is needed; (3) a single SHARED footer printed once after ALL notifications, dynamically naming the checks that actually fired. Crucially, the domain already models all of this: `InitService.check_drift()` returns an immutable `DriftReport` carrying `edited_prompts` / `missing_prompts` / `edited_templates` / `missing_templates` plus `prompts_drifted` / `templates_drifted` / `has_drift` properties. This workstream is therefore a PRESENTATION + CONFIG-SCHEMA change with ZERO domain, Port or signature change in the core. The only structural touch is module-local: the two notification helpers and `_run_cli_preflight_check` gain a `list[str]` return so the shared footer can be emitted once at a trailing point.

**Workstream B — `teddy plan` vestige.** The user asked to "remove `teddy plan` as a command; we just want `teddy start` and `teddy resume` as the main ones and `teddy execute` for sessionless." Investigation shows `teddy plan` is ALREADY gone as a registered CLI command (removed in commit `9753c179 feat(cli): add teddy init command and remove teddy plan CLI command`). The live surface is `start`, `init` (+ `prompts` / `config` / `templates`), `version`, `update`, `context`, `get-prompt`, `resume`, `execute`. What actually remains is residue: an ORPHANED `handle_plan_generation()` handler in `session_cli_handlers.py` (docstring "Logic for the 'plan' command") with NO production caller, two tests that exercise it, and stale `teddy plan` references in the invariant spec `interactive-session-workflow.md` (plus a stray "plan" in `cli.md`). This workstream is a bounded CLEANUP, not a live-command removal. (If the intent was broader than a cleanup, flag it before proceeding.)

**Locked copy.** Every user-facing string below was agreed with the user across the prior turns and is FINAL.

## Implementation Steps

### Workstream A — Split drift notifications, split toggles, add shared footer

#### Step 1: Split the notification toggles in the bundled config
- **File:** [src/teddy_executor/resources/config/config.yaml](/src/teddy_executor/resources/config/config.yaml)
- **Change:** Replace the `checks:` block's single `prompts_templates` key with two keys (`prompts`, `templates`), keep `update`, and add a comment per key. The block should read:

```yaml
# Notification Checks
# Independent toggles for user-facing notifications. All three default to
# enabled (true) when absent, so existing user configs keep working.
checks:
  prompts: true    # Notify when .teddy/prompts/ files differ from the bundled defaults.
  templates: true  # Notify when docs/templates/ files differ from the bundled defaults.
  update: true     # Notify when a newer TeDDy version is available (background fetch still runs).
```

The `checks.prompts_templates` key MUST NOT survive anywhere.

#### Step 2: Rewrite `_display_drift_notification` — per-channel, count-aware, returns fired keys
- **File:** [src/teddy_executor/adapters/inbound/session_cli_handlers.py](/src/teddy_executor/adapters/inbound/session_cli_handlers.py)
- **Change:** Give the helper the signature `_display_drift_notification(container: Container) -> list[str]`. Read `checks.prompts` (default `True`) and `checks.templates` (default `True`) INDEPENDENTLY via `IConfigService.get_setting`. Call `IInitUseCase.check_drift()`. For each channel that is BOTH enabled AND drifted, emit exactly ONE yellow line (`typer.echo(typer.style(..., fg=typer.colors.YELLOW))`) and append its key to the returned list. Emit the PROMPTS channel before the TEMPLATES channel; return `["checks.prompts"]`, `["checks.templates"]`, both, or `[]`. Locked wording for the prompts channel (mirror for templates with `docs/templates/`, `template(s)`, and `teddy init templates`). Let `d` = number of edited files, `m` = number of missing files, `n = d + m`; singular/plural is driven by `n == 1` (`prompt`/`prompts`, `differs`/`differ`, `is`/`are`):
  - changed only (`d > 0`, `m == 0`): `ℹ {n} {noun} in .teddy/prompts/ differ(s) from this version's defaults. To overwrite, run: teddy init prompts`
  - missing only (`d == 0`, `m > 0`): `ℹ {n} {noun} in .teddy/prompts/ is/are missing. To overwrite, run: teddy init prompts`
  - both (`d > 0`, `m > 0`): `ℹ {n} {noun} in .teddy/prompts/ differ(s) from this version's defaults ({d} changed, {m} missing). To overwrite, run: teddy init prompts`

#### Step 3: Make `_display_update_notification` return its fired key
- **File:** [src/teddy_executor/adapters/inbound/session_cli_handlers.py](/src/teddy_executor/adapters/inbound/session_cli_handlers.py)
- **Change:** Give the helper the signature `_display_update_notification(container: Container, cache_path: Path) -> list[str]`. Return `["checks.update"]` when the toggle is enabled AND a newer version is actually displayed; return `[]` when the toggle is disabled, the cache is absent/stale, or the cached version is not newer. Preserve ALL existing behavior (toggle gate, the prerelease-vs-stable upgrade command selection, and the debug-log on failure).

#### Step 4: Add the shared disable-footer helper
- **File:** [src/teddy_executor/adapters/inbound/session_cli_handlers.py](/src/teddy_executor/adapters/inbound/session_cli_handlers.py)
- **Change:** Add `_display_checks_footer(keys: list[str]) -> None`. No-op when `keys` is empty. Otherwise, dedupe and order the keys by the CANONICAL sequence `["checks.prompts", "checks.templates", "checks.update"]`, then emit ONE plain (uncolored) `typer.echo` line:
  - exactly one key: `You can disable this check in .teddy/config.yaml: {key}.`
  - more than one key: `You can disable these checks in .teddy/config.yaml: {k1}, {k2}.`

#### Step 5: Return drift keys from the preflight and wire the footer into both session handlers
- **File:** [src/teddy_executor/adapters/inbound/session_cli_handlers.py](/src/teddy_executor/adapters/inbound/session_cli_handlers.py)
- **Change:** Make `_run_cli_preflight_check(...) -> list[str]` return the drift fired-keys list produced by `_display_drift_notification(container)` on the HEALTHY path (and `[]` when there are no errors but no drift). Then, in BOTH `handle_new_session` and `handle_resume_session`: capture `fired = _display_update_notification(container, cache_path)` at its existing (early) call site, and after `_run_cli_preflight_check(...)` succeeds, extend `fired` with the keys it returned and call `_display_checks_footer(fired)` so the footer prints ONCE, after every notification. This arity/return change is MODULE-LOCAL (no external callers) and therefore Green-to-Green.

#### Step 6: Update the bundled-config toggle contract test
- **File:** [tests/suites/unit/test_bundled_config_notification_toggles.py](/tests/suites/unit/test_bundled_config_notification_toggles.py)
- **Change:** Update the assertions to require `checks.prompts is True` and `checks.templates is True`, and to assert that `checks.prompts_templates` is ABSENT. Keep the `checks.update is True` assertion and the module docstring consistent with the new keys.

#### Step 7: Repoint the toggle unit tests and add footer coverage
- **File:** [tests/suites/unit/adapters/inbound/test_session_notification_toggles.py](/tests/suites/unit/adapters/inbound/test_session_notification_toggles.py)
- **Change:** Replace every `checks.prompts_templates` gate reference with `checks.prompts` (and add an analogous `checks.templates` gate test). Keep the "absent toggle defaults to enabled" characterization. Add footer coverage: when `checks.prompts` fires alongside `checks.update`, `_display_checks_footer` emits `You can disable these checks in .teddy/config.yaml: checks.prompts, checks.update.`; when only one fires it uses "this check"; a disabled channel is omitted from the footer.

#### Step 8: Extend the drift acceptance tests
- **File:** [tests/suites/acceptance/test_preflight_drift_notification.py](/tests/suites/acceptance/test_preflight_drift_notification.py)
- **Change:** Keep the two existing scenarios (their `teddy init prompts` / `teddy init templates` substring assertions remain valid under the new per-channel wording) and extend them to assert that the shared footer line (`You can disable ... in .teddy/config.yaml: ...`) is present.

### Workstream B — Retire the `teddy plan` vestige

#### Step 9: Delete the orphaned handler
- **File:** [src/teddy_executor/adapters/inbound/session_cli_handlers.py](/src/teddy_executor/adapters/inbound/session_cli_handlers.py)
- **Change:** Delete the entire `handle_plan_generation()` function (docstring "Logic for the 'plan' command"). It has NO production caller. Do NOT delete `detect_session_context()` — it is still used by `handle_context_gathering`.

#### Step 10: Remove the handler's unit test and import
- **File:** [tests/suites/unit/adapters/inbound/test_session_preflight_wiring.py](/tests/suites/unit/adapters/inbound/test_session_preflight_wiring.py)
- **Change:** Remove `handle_plan_generation` from the import block and delete `test_handle_plan_generation_halts_on_preflight_failure`.

#### Step 11: Remove the integration scenario
- **File:** [tests/suites/integration/core/services/test_session_orchestration_integration.py](/tests/suites/integration/core/services/test_session_orchestration_integration.py)
- **Change:** Delete `test_teddy_plan_generates_plan_file` (and its local `from teddy_executor.adapters.inbound.session_cli_handlers import handle_plan_generation`).

#### Step 12: Reconcile the session-workflow invariant spec
- **File:** [docs/project/specs/invariants/interactive-session-workflow.md](/docs/project/specs/invariants/interactive-session-workflow.md)
- **Change:** Remove `teddy plan` as a documented CLI command: the `### teddy plan` command section, the flowchart node referencing `` `teddy plan` or `resume` ``, and the two prose references. Where the section documents genuinely real turn-lifecycle behavior (implicit context generation, plan.md generation), recast it as an INTERNAL phase of `start`/`resume` rather than deleting the behavioral description outright.

#### Step 13: Update the CLI adapter doc
- **File:** [docs/architecture/adapters/inbound/cli.md](/docs/architecture/adapters/inbound/cli.md)
- **Change:** In the "Preflight Notifications (Drift & Update)" section: change "the shared slot reached by `start`, `plan` and `resume`" to "reached by `start` and `resume`", and rewrite the drift bullet to describe the two INDEPENDENT toggles (`checks.prompts` / `checks.templates`), the per-channel count-aware lines, and the single shared disable-footer.

## Verification

1. `uv run pytest tests/suites/unit/test_bundled_config_notification_toggles.py` passes and asserts `checks.prompts` / `checks.templates` (and no `checks.prompts_templates`).
2. `uv run pytest tests/suites/unit/adapters/inbound/test_session_notification_toggles.py` passes, including the new footer assertions.
3. `uv run pytest tests/suites/acceptance/test_preflight_drift_notification.py` passes.
4. `git grep -n "handle_plan_generation" -- src tests` returns NO hits.
5. `git grep -n "checks.prompts_templates" -- src tests docs` returns NO hits.
6. `git grep -ni "teddy plan" -- src tests docs` returns NO hits (or only clearly-marked historical references).
7. Manual: in a workspace with one edited prompt and one missing template, `teddy start -y -m hi` prints one prompts line, one templates line, and a single footer `You can disable these checks in .teddy/config.yaml: checks.prompts, checks.templates.`
8. Manual: with `checks.prompts: false`, the prompts line is suppressed AND `checks.prompts` is absent from the footer.
9. `make test` (full suite, no filters) is GREEN.
