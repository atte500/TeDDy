# Slice: Refine CLI Preflight Notifications and Retire the `teddy plan` Vestige
- **Status:** In Progress
- **Milestone:** N/A (ad-hoc)
- **Specs:** [interactive-session-workflow.md](/docs/project/specs/invariants/interactive-session-workflow.md)
- **Prototype:** N/A
- **Component Docs:** [cli.md](/docs/architecture/adapters/inbound/cli.md), [init_service.md](/docs/architecture/core/services/init_service.md)
- **Scope Slug:** `preflight-notifications`

## Business Goal

Make the CLI's preflight notifications accurate, independently controllable, and self-describing (including a discoverable way to silence them), and remove the dead code and stale documentation left behind when the `teddy plan` command was retired. Source: [task brief](/docs/project/tasks/01-refine-preflight-notifications.md).

## Scenarios

> As a TeDDy user, I want accurate, independent preflight notifications so I can act on prompt/template drift and silence the checks I don't need.

```gherkin
Given a workspace whose .teddy/prompts/ contains one prompt that differs from the bundled default
When the user runs `teddy start`
Then the preflight prints exactly one yellow prompts line naming `teddy init prompts`
And prints a single shared disable-footer naming `checks.prompts`
```

```gherkin
Given a workspace whose docs/templates/ is missing one bundled template
When the user runs `teddy start`
Then the preflight prints exactly one yellow templates line naming `teddy init templates`
And prints a single shared disable-footer naming `checks.templates`
```

```gherkin
Given a workspace with prompt drift, template drift, and a newer TeDDy version cached
When the user runs `teddy start`
Then the preflight prints the prompts line, the templates line, and the update line
And prints exactly one footer: "You can disable these checks in .teddy/config.yaml: checks.prompts, checks.templates, checks.update."
```

## Edge Cases

- **Disabled channel suppression**: If `checks.prompts: false`, then the prompts drift line is suppressed AND `checks.prompts` is omitted from the footer, because the check never fired.
- **Absent toggle defaults to enabled**: If the `checks` block (or a single key) is absent, then the corresponding check defaults to ENABLED, so existing user configs keep behaving as before.
- **Singular vs plural footer**: If exactly one check fires, then the footer uses "this check"; two or more use "these checks".
- **No notifications**: If nothing drifts and no update is available, then the footer is a no-op (no line printed).
- **Count-aware wording**: If a channel has only CHANGED files, then it says the files "differ from this version's defaults"; only MISSING files -> "is/are missing"; both -> "differ ... (d changed, m missing)". Singular/plural is driven by `n == d + m == 1`.
- **Orphaned handler**: If `handle_plan_generation` is deleted, then no live behavior changes, because it has no production caller.

## Key Unknowns

- [x] [Technical] `DriftReport` shape: confirmed `edited_prompts`/`missing_prompts`/`edited_templates`/`missing_templates` (tuples) plus `prompts_drifted`/`templates_drifted`/`has_drift` properties in [drift_report.py](/src/teddy_executor/core/domain/models/drift_report.py).
- [x] [Technical] Seam locality: `_run_cli_preflight_check` (callers at `session_cli_handlers.py:486/900/1027`), `_display_drift_notification` (caller at `:632`), and `_display_update_notification` (callers at `:469/1019`) are ALL module-local -> the return-arity changes are Green-to-Green (no Shared Seam, no Contract->Migration->Cleanup partition).
- [x] [Technical] Removal-test convention: the project pins removals with `importlib.util.find_spec(...) is None` guards (e.g. [test_console_plan_reviewer_removal.py](/tests/suites/unit/adapters/inbound/test_console_plan_reviewer_removal.py)). `handle_plan_generation` is intra-module, so its retirement is verified by the `git grep` gate plus removal of its two existing tests rather than a module-find_spec guard.

## Implementation Plan

Workstream A is a PRESENTATION + CONFIG-SCHEMA change with ZERO core-domain, Port, or signature change. The domain already models drift via `InitService.check_drift() -> DriftReport`. The only structural touch is module-local: three helpers gain a `list[str]` return so a shared footer can be emitted once at a trailing point.

**Config schema.** `config.yaml`'s `checks:` block loses `prompts_templates` and gains `prompts` + `templates` (keeping `update`), each read independently via `IConfigService.get_setting(key, True)`. The old combined key MUST NOT survive anywhere. The bundled-config contract test asserts the two new keys and the ABSENCE of the old one.

**Drift notification.** `_display_drift_notification(container) -> list[str]` reads `checks.prompts` and `checks.templates` INDEPENDENTLY, calls `check_drift()`, and for each channel that is BOTH enabled AND drifted emits exactly ONE yellow count-aware line (prompts before templates), appending its key to the returned list. Wording (prompts; mirror for templates with `docs/templates/`, `template(s)`, `teddy init templates`), with `d`=edited, `m`=missing, `n=d+m` and singular/plural driven by `n == 1`:
- changed only (`d>0`, `m==0`): `ℹ {n} {noun} in .teddy/prompts/ {differs|differ} from this version's defaults. To overwrite, run: teddy init prompts`
- missing only (`d==0`, `m>0`): `ℹ {n} {noun} in .teddy/prompts/ {is|are} missing. To overwrite, run: teddy init prompts`
- both (`d>0`, `m>0`): `ℹ {n} {noun} in .teddy/prompts/ {differs|differ} from this version's defaults ({d} changed, {m} missing). To overwrite, run: teddy init prompts`

**Update notification.** `_display_update_notification(container, cache_path) -> list[str]` returns `["checks.update"]` when the toggle is enabled AND a newer version is actually displayed, else `[]` (preserving the toggle gate, the prerelease-vs-stable upgrade-command selection, and the debug-log-on-failure).

**Shared footer.** `_display_checks_footer(keys: list[str]) -> None` no-ops on empty input; otherwise it dedupes and orders keys by the canonical sequence `["checks.prompts", "checks.templates", "checks.update"]` and emits ONE plain (uncolored) line: singular -> `You can disable this check in .teddy/config.yaml: {key}.`; plural -> `You can disable these checks in .teddy/config.yaml: {k1}, {k2}.`

**Wiring.** `_run_cli_preflight_check(...) -> list[str]` returns the drift keys from `_display_drift_notification(container)` on the HEALTHY path (`[]` when there are no errors but no drift). In `handle_new_session`/`handle_resume_session`, capture the update keys at the early call site, extend them with the preflight return after success, and call `_display_checks_footer(...)` ONCE. HAZARD: three existing tests in `test_session_cli_handlers.py` (patch targets at lines 379/475/552) stub `_run_cli_preflight_check`; D5 must set their stub `.return_value = []` so `list.extend`/`+` stays type-correct — a Local migration folded into the same atomic change (not a Systemic Regression).

**Workstream B (cleanup).** Delete the orphaned `handle_plan_generation()` (no production caller) and its two tests; reconcile the invariant spec and the CLI component doc. The `cli.md` bullet is finalized in the As-Built Update (Phase 4) once the code reality is fixed.

## Deliverables

- [x] **Logic** - Split the bundled notification toggles: replace `checks.prompts_templates` with `checks.prompts` + `checks.templates` (keep `checks.update`) in `src/teddy_executor/resources/config/config.yaml`; update `tests/suites/unit/test_bundled_config_notification_toggles.py` to require the two new keys and assert the old key is ABSENT.
- [ ] **Logic** - Rewrite `_display_drift_notification(container) -> list[str]` to read `checks.prompts`/`checks.templates` independently, emit ONE count-aware yellow line per CHANGED/MISSING channel (prompts before templates), and return the fired keys; repoint `tests/suites/unit/adapters/inbound/test_session_notification_toggles.py` to the new keys, add a `checks.templates` gate test and count-aware wording coverage.
- [ ] **Logic** - Make `_display_update_notification(container, cache_path) -> list[str]` return `["checks.update"]` when the notification fires (toggle enabled AND a newer version displayed) else `[]`, preserving all existing behavior; add a unit test for the return value.
- [ ] **Logic** - Add `_display_checks_footer(keys: list[str]) -> None` (no-op on empty; otherwise ONE plain line ordering the deduped keys by the canonical sequence, "this check" singular / "these checks" plural); add unit tests.
- [ ] **Wiring** - Return the drift fired-keys from `_run_cli_preflight_check(...) -> list[str]` and wire the shared footer into `handle_new_session` and `handle_resume_session` (capture the update keys, extend with the preflight return, call `_display_checks_footer` once) — adapting the three `test_session_cli_handlers.py` stubs to `.return_value = []`; extend `tests/suites/acceptance/test_preflight_drift_notification.py` to assert the shared footer. This is the Tracer Bullet / final behavioral gate.
- [ ] **Cleanup** - Delete the orphaned `handle_plan_generation()` from `session_cli_handlers.py`; remove `test_handle_plan_generation_halts_on_preflight_failure` (`tests/suites/unit/adapters/inbound/test_session_preflight_wiring.py` + its import) and `test_teddy_plan_generates_plan_file` (`tests/suites/integration/core/services/test_session_orchestration_integration.py` + its local import).
- [ ] **Cleanup** - Reconcile the docs: retire `teddy plan` from `docs/project/specs/invariants/interactive-session-workflow.md` (command section, flowchart node, two prose references — recasting genuine turn-lifecycle behavior as an internal phase of `start`/`resume`) and update the drift bullet in `docs/architecture/adapters/inbound/cli.md` to describe the two independent toggles, per-channel count-aware lines, and the shared footer.

## Implementation Notes

### D1 — Split the bundled notification toggles (Logic)

**Production change.** `src/teddy_executor/resources/config/config.yaml`: the `checks:` block's combined `prompts_templates` key was replaced by two independent keys `prompts` + `templates` (keeping `update`), each documented with a per-key comment. The old combined key is retired outright (the feature is unreleased, so no backward-compatibility fallback was added).

**Contract test.** `tests/suites/unit/test_bundled_config_notification_toggles.py`: `test_bundled_config_declares_notification_toggles` now requires `checks.prompts is True` and `checks.templates is True` (retaining `checks.update is True`), and a new sibling `test_bundled_config_retires_combined_prompts_templates_key` asserts the retired combined key is ABSENT. The module docstring was updated to describe the three independent toggles.

**Red-Green evidence.** Red (Turn 6): the repointed contract test produced EXACTLY the predicted two coupled `AssertionError`s — `Bundled config.yaml must declare 'checks.prompts: true'; got: None` and `Bundled config.yaml must NOT declare the retired combined 'checks.prompts_templates' key; got: True`, with the parsed mapping `{'prompts_templates': True, 'update': True}`. Green (Turn 7): after the single `config.yaml` edit, the targeted run returned `2 passed`.

**Green-to-Green.** Integration gate (Turn 8, `make test`, full suite, no filters) → `1708 passed, 5 skipped`. The change is green-to-green by construction: the production `_display_drift_notification` still reads `config.get_setting("checks.prompts_templates", True)`, which now returns its `True` default because the bundled key is absent — so the drift advice fires exactly as before and the acceptance suite stayed green. The two remaining live references to the old key (the production read in `_display_drift_notification` and the mocked side_effect in `test_session_notification_toggles.py`) are intentionally left for D2, which repoints them to the two new keys. This is a planned, scoped hand-off, NOT latent debt.

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
