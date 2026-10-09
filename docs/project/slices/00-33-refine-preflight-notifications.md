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
- [x] **Logic** - Rewrite `_display_drift_notification(container) -> list[str]` to read `checks.prompts`/`checks.templates` independently, emit ONE count-aware yellow line per CHANGED/MISSING channel (prompts before templates), and return the fired keys; repoint `tests/suites/unit/adapters/inbound/test_session_notification_toggles.py` to the new keys, add a `checks.templates` gate test and count-aware wording coverage.
- [x] **Logic** - Make `_display_update_notification(container, cache_path) -> list[str]` return `["checks.update"]` when the notification fires (toggle enabled AND a newer version displayed) else `[]`, preserving all existing behavior; add a unit test for the return value.
- [x] **Logic** - Add `_display_checks_footer(keys: list[str]) -> None` (no-op on empty; otherwise ONE plain line ordering the deduped keys by the canonical sequence, "this check" singular / "these checks" plural); add unit tests.
- [x] **Wiring** - Return the drift fired-keys from `_run_cli_preflight_check(...) -> list[str]` and wire the shared footer into `handle_new_session` and `handle_resume_session` (capture the update keys, extend with the preflight return, call `_display_checks_footer` once) — adapting the three `test_session_cli_handlers.py` stubs to `.return_value = []`; extend `tests/suites/acceptance/test_preflight_drift_notification.py` to assert the shared footer. This is the Tracer Bullet / final behavioral gate.
- [x] **Cleanup** - Delete the orphaned `handle_plan_generation()` from `session_cli_handlers.py`; remove `test_handle_plan_generation_halts_on_preflight_failure` (`tests/suites/unit/adapters/inbound/test_session_preflight_wiring.py` + its import) and `test_teddy_plan_generates_plan_file` (`tests/suites/integration/core/services/test_session_orchestration_integration.py` + its local import).
- [x] **Cleanup** - Reconcile the docs: retire `teddy plan` from `docs/project/specs/invariants/interactive-session-workflow.md` (command section, flowchart node, two prose references — recasting genuine turn-lifecycle behavior as an internal phase of `start`/`resume`) and update the drift bullet in `docs/architecture/adapters/inbound/cli.md` to describe the two independent toggles, per-channel count-aware lines, and the shared footer.

## Implementation Notes

### D1 — Split the bundled notification toggles (Logic)

**Production change.** `src/teddy_executor/resources/config/config.yaml`: the `checks:` block's combined `prompts_templates` key was replaced by two independent keys `prompts` + `templates` (keeping `update`), each documented with a per-key comment. The old combined key is retired outright (the feature is unreleased, so no backward-compatibility fallback was added).

**Contract test.** `tests/suites/unit/test_bundled_config_notification_toggles.py`: `test_bundled_config_declares_notification_toggles` now requires `checks.prompts is True` and `checks.templates is True` (retaining `checks.update is True`), and a new sibling `test_bundled_config_retires_combined_prompts_templates_key` asserts the retired combined key is ABSENT. The module docstring was updated to describe the three independent toggles.

**Red-Green evidence.** Red (Turn 6): the repointed contract test produced EXACTLY the predicted two coupled `AssertionError`s — `Bundled config.yaml must declare 'checks.prompts: true'; got: None` and `Bundled config.yaml must NOT declare the retired combined 'checks.prompts_templates' key; got: True`, with the parsed mapping `{'prompts_templates': True, 'update': True}`. Green (Turn 7): after the single `config.yaml` edit, the targeted run returned `2 passed`.

**Green-to-Green.** Integration gate (Turn 8, `make test`, full suite, no filters) → `1708 passed, 5 skipped`. The change is green-to-green by construction: the production `_display_drift_notification` still reads `config.get_setting("checks.prompts_templates", True)`, which now returns its `True` default because the bundled key is absent — so the drift advice fires exactly as before and the acceptance suite stayed green. The two remaining live references to the old key (the production read in `_display_drift_notification` and the mocked side_effect in `test_session_notification_toggles.py`) are intentionally left for D2, which repoints them to the two new keys. This is a planned, scoped hand-off, NOT latent debt.

### D2 — Rewrite `_display_drift_notification` to per-channel count-aware output (Logic)

**Production change.** `src/teddy_executor/adapters/inbound/session_cli_handlers.py`: the combined `_display_drift_notification(container) -> None` was replaced by a pure `_format_drift_clause(noun_singular, noun_plural, target_dir, edited, missing) -> str` helper plus a rewritten `_display_drift_notification(container) -> list[str]`. The rewritten helper reads `checks.prompts` and `checks.templates` INDEPENDENTLY (each defaulting to `True`), calls `IInitUseCase.check_drift()`, emits exactly ONE count-aware yellow line per channel that is BOTH enabled AND drifted (prompts before templates), and returns the fired keys in canonical order. The return value is currently discarded by its sole caller (`_run_cli_preflight_check`), so widening `-> None` to `-> list[str]` is Green-to-Green; threading the return to the shared footer is D5's job, not this deliverable's.

**Test change.** `tests/suites/unit/adapters/inbound/test_session_notification_toggles.py`: repointed from the retired `checks.prompts_templates` to the two independent keys, added a `checks.templates` suppression test, three parameterized count-aware wording cases (changed-only / missing-only / both), and a both-channel ordering + fired-keys test.

**Red-Green evidence.** Red (Turn 11): `7 failed, 2 passed` — the four gate/characterization tests plus the three count-aware cells failed because the helper still read the retired `checks.prompts_templates` (returning its `True` default via the absent key) and emitted the old combined sentence (`ℹ Prompt/template drift detected. To restore the bundled defaults, run: teddy init prompts`). Green (Turn 12): `9 passed`.

**Integration + Local Recovery.** The Phase 3 full-suite gate (Turn 19, `8 failed, 1705 passed`) surfaced 8 regressions traced to the new `len(report.edited_prompts)`/`len(report.missing_prompts)` calls: three session-handler test files registered a loose `Mock(spec=IInitUseCase)` whose `check_drift()` returned a dynamic Mock (no `__len__`), raising `object of type 'Mock' has no len()` that `handle_new_session`'s broad `except Exception` swallowed into `typer.Exit(1)`. Classified as a **Local Flaw** (test-only fix). Local Recovery (Turn 22) configured those doubles to return a contract-faithful empty `DriftReport()` in `test_session_replan_loop.py` (2 sites), `test_session_start_resequencing.py` (3 sites), and `test_resume_message_threading.py` (registered a configured `IInitUseCase`), and seeded a harness-level default in `tests/harness/setup/test_environment.py::_register_system_mocks`. The full suite then returned `1713 passed, 5 skipped`.

**Harness artifact.** A bare `make test` can return a false `FAILURE: Interactive prompt detected` sentinel (the `ShellAdapter` heuristic replaces the entire stream when a non-zero exit coincides with a prompt-like substring) on the ~1700-line output. Observation was therefore made via `spikes/d2_diagnostic.sh` (redirect to a file + exit 0). That temporary script is deleted in the Phase 5 teardown.

### D3 — Return the fired update key from `_display_update_notification` (Logic)

**Production change.** `src/teddy_executor/adapters/inbound/session_cli_handlers.py`: `_display_update_notification(container, cache_path) -> None` was widened to `-> list[str]`. The helper now returns `["checks.update"]` at the point where the newer-version notification is actually echoed, and `[]` at every non-firing path (toggle disabled, cache absent, no `latest_version`, a non-newer cached version, and the broad `except Exception` debug-log branch). All existing behaviour is preserved: the `checks.update` toggle gate (default `True`), the prerelease-vs-stable upgrade-command selection, and the debug-log-on-failure. Both call sites (`handle_new_session`, `handle_resume_session`) still discard the return, so the arity widening is Green-to-Green; threading the fired key into the shared footer is D5's job.

**Test change.** `tests/suites/unit/adapters/inbound/test_session_notification_toggles.py`: extended `test_update_notification_suppressed_when_update_toggle_disabled` to assert `fired == []`, and added `test_update_notification_reports_fired_key_when_it_fires` (asserts `fired == ["checks.update"]`) plus `test_update_notification_returns_empty_when_no_update_available` (asserts `fired == []` with an absent cache).

**Red-Green evidence.** Red (Turn 26): `3 failed, 8 passed` — the three return-value assertions failed on `assert None == []` / `assert None == ["checks.update"]` because the helper still returned `None`. Recon (Turn 27) extracted the byte-exact body (lines 455–491). Green (Turn 28): `11 passed`.

**Integration.** The Phase 3 full-suite gate (Turn 29, observed via `spikes/d3_diagnostic.sh`) returned `1715 passed, 5 skipped` — D2's committed baseline (`1713 passed, 5 skipped`) plus D3's two net-new test functions. No regressions. The temporary `spikes/d3_diagnostic.sh` observer is deleted in the Phase 5 teardown.

### D4 — Add the shared disable-footer helper (Logic)

**Production change.** `src/teddy_executor/adapters/inbound/session_cli_handlers.py`: added `_display_checks_footer(keys: list[str]) -> None` immediately before `_display_update_notification`. It no-ops on an empty list; otherwise it dedupes the keys, orders them by the canonical sequence `("checks.prompts", "checks.templates", "checks.update")`, and emits exactly ONE plain (uncolored) `typer.echo` line — singular `You can disable this check in .teddy/config.yaml: {key}.` for exactly one key, plural `You can disable these checks in .teddy/config.yaml: {k1}, {k2}.` for more than one. The helper is inert until D5 wires it (it has no caller yet), so the change is additive and Green-to-Green.

**Test change.** `tests/suites/unit/adapters/inbound/test_session_notification_toggles.py`: added `_display_checks_footer` to the module's top-level import and four tests — empty no-op; singular wording; plural wording + canonical ordering (keys passed deliberately out of order); and dedup of repeated keys.

**Red-Green evidence.** Red (Turn 40): the top-level import drove a collection ERROR with `ImportError: cannot import name '_display_checks_footer' from 'teddy_executor.adapters.inbound.session_cli_handlers'` (`1 error in 1.12s`). Green (Turn 41): the targeted run returned `15 passed` (the 11 pre-existing tests plus the four new footer tests).

**Integration.** The Phase 3 full-suite gate (Turn 42, observed via a redirect + `exit 0` wrapper to sidestep the EXECUTE-harness false-positive prompt sentinel) returned `1719 passed, 5 skipped` — D3's committed baseline (`1715 passed, 5 skipped`) plus D4's four net-new test functions. No regressions.

### D5 — Wire the shared disable-footer into the session preflight (Wiring)

**Production change.** `src/teddy_executor/adapters/inbound/session_cli_handlers.py`: narrowed the wiring so the shared footer is emitted ONCE, after every preflight notification, in both session entry points. `_run_cli_preflight_check(...)` widened from `-> None` to `-> list[str]`, returning the drift fired-keys from `_display_drift_notification(container)` on the HEALTHY path (the error path still raises, so the footer never prints on failure). In `handle_new_session`, the early call site now captures `fired = _display_update_notification(container, cache_path)`, then wraps the preflight call in `fired.extend(...)` and emits `_display_checks_footer(fired)` once, immediately before `_echo_config_success`. `handle_resume_session` mirrors this (capture at its update-notify site, `fired.extend(...)` around the preflight, then `_display_checks_footer(fired)` before resolving the session name). The arity change is MODULE-LOCAL — all three `_run_cli_preflight_check` call sites are internal — so it is Green-to-Green.

**Test change.** `tests/suites/acceptance/test_preflight_drift_notification.py`: both existing scenarios were extended to assert the shared disable-footer; the FIRST scenario (one edited prompt) fires BOTH channels because the workspace also has eleven missing templates, so its assertion is the PLURAL `You can disable these checks in .teddy/config.yaml: checks.prompts, checks.templates.`, while the SECOND (templates-only) asserts the singular footer. `tests/suites/unit/adapters/inbound/test_session_cli_handlers.py`: the three `_run_cli_preflight_check` stubs were adapted to return `[]` (so the handlers' new `fired.extend(...)` never receives `None`), and the sole `_display_update_notification` stub was corrected from `None` to `[]`.

**Red-Green evidence.** Red (Turn 47): the acceptance file reported `2 failed`, both being the new footer assertions, with the pre-existing `teddy init prompts` / `teddy init templates` assertions still holding. Green (Turn 51, after a Turn 50 diagnosis): `16 passed`. The two failures were (1) the `_display_update_notification` stub returning `None`, so `fired.extend([])` raised `AttributeError: 'NoneType' object has no attribute 'extend'` (swallowed by the handler's broad `except Exception` → `typer.Exit(1)`), and (2) the over-strict singular footer assertion in the first scenario, which genuinely fires both channels — matching the task brief's verification item 7.

**Integration.** The Phase 3 full-suite gate (Turn 52, observed via a redirect + `|| true` guard + `exit 0` wrapper to sidestep the EXECUTE-harness false-positive prompt sentinel) returned `1719 passed, 5 skipped` — unchanged from D4's committed baseline, since D5 added no new test functions. No regressions.

### D6 — Retire the orphaned `teddy plan` handler and its tests (Cleanup)

**Production change.** `src/teddy_executor/adapters/inbound/session_cli_handlers.py`: deleted the entire orphaned `handle_plan_generation()` function (docstring "Logic for the 'plan' command"), which has NO production caller after the `teddy plan` CLI command was retired in commit `9753c179`. Deleting the handler left its sole-usage `from teddy_executor.core.ports.inbound.planning_use_case import IPlanningUseCase` module-top import orphaned (confirmed by a grep returning ONLY line 13), so that unused import was pruned in the same change — a direct, in-scope consequence (Ruff F401). `detect_session_context()` was deliberately preserved (still used by `handle_context_gathering`).

**Test change.** `tests/suites/unit/adapters/inbound/test_session_preflight_wiring.py`: removed `handle_plan_generation` from the `session_cli_handlers` import block and deleted the whole `test_handle_plan_generation_halts_on_preflight_failure` test; the now-orphaned `IPlanningUseCase` module-top import (its sole consumer was the deleted test's `env.mock_port(IPlanningUseCase)`) was likewise pruned. `tests/suites/integration/core/services/test_session_orchestration_integration.py`: deleted `test_teddy_plan_generates_plan_file`, including its function-local `from ... import handle_plan_generation`.

**Red-Green evidence.** Red (Turn 57): deleting the production handler drove `1 failed, 10 passed, 1 error` — `test_session_preflight_wiring.py` failed at COLLECTION (whole-file `ImportError: cannot import name 'handle_plan_generation'`) and `test_teddy_plan_generates_plan_file` FAILED at RUNTIME (its in-body local import raising the same `ImportError`). The same run's `IPlanningUseCase` grep returned ONLY line 13, proving the production import was orphaned. Green (Turn 59): the four EDITs (production import prune + wiring-test import/test removal + integration-test deletion) returned `34 passed`, and `git grep handle_plan_generation -- src tests` was EMPTY. Refactor (Turn 60): pruning the residual orphaned `IPlanningUseCase` test import kept `34 passed` with both greps EMPTY — verification item 4 is satisfied.

**Integration.** The Phase 3 full-suite gate (Turn 61, observed via a redirect + `|| true` guard + `exit 0` wrapper to sidestep the EXECUTE-harness false-positive prompt sentinel) returned `1717 passed, 5 skipped` — D5's committed baseline (`1719 passed, 5 skipped`) minus the two removed test functions. No regressions.

### D7 — Retire `teddy plan` from the docs and document the split drift checks (Cleanup)

**Spec change.** `docs/project/specs/invariants/interactive-session-workflow.md`: removed `teddy plan` as a documented CLI command. The flowchart's entry node `` `teddy plan` or `resume` `` became `` `teddy start` or `resume` ``; the `### teddy plan` command section was recast as `### Plan Generation (Internal)`, preserving the genuinely real turn-lifecycle behavior (implicit context generation, plan.md generation) as an INTERNAL phase of `start`/`resume` rather than deleting the behavioral description outright; and the two remaining prose references were recast to point at that internal phase.

**Component-doc change (As-Built).** `docs/architecture/adapters/inbound/cli.md`: the "Preflight Notifications (Drift & Update)" section's "reached by `start`, `plan` and `resume`" became "reached by `start` and `resume`"; the drift bullet was rewritten to describe the two INDEPENDENT toggles (`checks.prompts` / `checks.templates`), the per-channel count-aware lines, and the NEW single shared disable-footer; and "Both toggles" was corrected to "All three toggles" to match the three independent `checks.*` keys. This rewrite IS the Phase 4 Step 4 As-Built Component-Doc update for the CLI adapter.

**Red-Green evidence (docs-only).** D7 is a Markdown-only reconciliation with NO executable code seam, so no Red test loop applies — the change itself (Turn 66) was the "Green". The verification EXECUTE (Turn 66) confirmed the two target docs carry NO live `teddy plan` or `checks.prompts_templates` reference; the residual `teddy plan` hits are confined to historical slice/task-brief artifacts plus the `parser_metadata.md` case-insensitive false positive ("a TeDDy plan" = the plan document), and the residual `checks.prompts_templates` hits to the absence-asserting contract test (`test_bundled_config_notification_toggles.py`) plus historical notes — verification items 5 and 6 are therefore satisfied as scoped.

**Integration.** The Phase 3 full-suite gate (Turn 67, observed via a redirect + `|| true` guard + `exit 0` wrapper to sidestep the EXECUTE-harness false-positive prompt sentinel) returned `1717 passed, 5 skipped` — IDENTICAL to D6's committed baseline, since D7 is documentation-only and adds no tests. No regressions.

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
