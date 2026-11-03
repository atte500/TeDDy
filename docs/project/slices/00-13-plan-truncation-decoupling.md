# Slice: Plan Truncation Decoupling

- **Status:** In Progress
- **Milestone:** N/A (ad-hoc, from Case File 76)
- **Depends On:** N/A
- **Specs:** N/A
- **Prototype:** N/A
- **Component Docs:** [SessionOrchestrator](/docs/architecture/core/services/session_orchestrator.md), [SessionService](/docs/architecture/core/services/session_service.md), [LocalFileSystemAdapter](/docs/architecture/adapters/outbound/local_file_system_adapter.md), [TextualPlanReviewer](/docs/architecture/adapters/inbound/textual_plan_reviewer.md)
- **Scope Slug:** `plan-truncation`

## Goal

Decouple plan-file truncation from the READ-tool `read.max_lines` cap. Display reads truncate at a plan-specific limit with a hint-less notice, while correctness reads always see the full plan. This fixes the user-visible truncation in the TUI viewer/refinement and removes the two correctness hazards — resume write-back data loss and `## Message` marker miss on long plans — captured in Case File 76.

## Context

- Case File 76 verifies the root cause: `LocalFileSystemAdapter.read_file` head-truncates at `read.max_lines` (default 1000) via `truncate_lines(content, max_lines=self.max_read_lines, direction="head", action_type="read")`, appending the READ-tool hint `[Content truncated: ... Use the 'Lines' parameter ...]`. Six plan-read call sites route through it, so long plans are truncated and hint-stamped wherever they are viewed, refined, parsed, resumed, or preserved.
- `IFileSystemManager.read_raw_file` exists on the port and returns full untruncated content. `read_files_in_vault` already uses it for context assembly, so bypassing the cap is an established pattern in the codebase.
- `truncate_lines(content, max_lines, direction="head", hint="")` supports hint-less truncation: when `hint` is empty and `action_type` is absent, no banner is emitted. A plain custom hint string can be passed through the `hint` parameter.
- `AppConfig` in `core/domain/models/config_schema.py` composes nested frozen dataclasses (`ReadConfig.max_lines = 1000`, `ExecuteConfig`, `EditConfig`, etc.) via `field(default_factory=...)`. `IConfigService.get_setting("plan.max_lines", default)` resolves dotted keys through the same mechanism.
- `session_orchestrator._prepare_plan_parsing` reads the plan via `read_file` only when `plan_content` is None. The greenfield create path already feeds the full `plan_content` string into the parser, so routing through `read_raw_file` matches established behavior rather than introducing a new performance surface.
- The reviewer is composed in `registries/reviewer.py::tui_factory`, which constructs `TextualPlanReviewer` from container-resolved ports. Neither `TextualPlanReviewer` nor its `ReviewerApp` currently carries a config handle, so the slice adds an optional `config_service: IConfigService | None = None` to both (defaulting to `None`) to keep existing `ReviewerApp(` and `TextualPlanReviewer(` test construction sites green.
- `read_raw_file` is implemented concretely on `LocalFileSystemAdapter` (line 301), not just declared on the port, so correctness reads are directly callable today.

## Scenarios

> As a developer viewing or refining a long plan, I want the plan displayed in full (or truncated at a plan-appropriate limit) so that I can review and edit it without a misleading READ-tool hint.

```gherkin
Given a plan file longer than plan.max_lines
When I open the plan in the TUI viewer
Then the editor displays the first plan.max_lines lines
And the content is succeeded by a hint-less notice "[Showing first N of M lines.]"
And the "Use the 'Lines' parameter" hint is absent
```

> As a developer resuming or executing a long plan, I want the plan parsed from full untruncated content so that the plan executes correctly and is preserved across turns.

```gherkin
Given a plan file longer than read.max_lines (1000)
When I execute or resume that plan
Then parsing consumes the full untruncated plan content
And the plan is not truncated on write-back to disk
And a plan turn containing "## Message" beyond line 1000 is preserved in session.context
```

## Edge Cases

- **At the cap:** A plan file with exactly `plan.max_lines` lines is not truncated and carries no notice, because `truncate_lines` preserves content at or below the cap.
- **Empty plan:** An empty plan file renders empty and carries no notice, because `truncate_lines` short-circuits on empty content.
- **Zero or negative cap:** If `plan.max_lines` is configured `<= 0`, `truncate_lines` returns content unchanged. Document the defensive behavior; no new handling is added.
- **Config default:** `plan.max_lines` defaults to `5000` when absent from config, so existing workspaces require no migration.
- **Marker detection:** `_is_preserved_turn` searches full plan content for `## Message`, so a plan whose `## Message` section falls beyond the old 1000-line cap is now correctly preserved.

## Key Unknowns

None. Every technical question was resolved during Discovery:
- `read_raw_file` exists on `IFileSystemManager` (verified in `core/ports/outbound/file_system_manager.py`).
- `truncate_lines` supports hint-less truncation (verified in `core/utils/string.py`).
- Config schema uses nested frozen dataclasses resolvable via `IConfigService.get_setting` (verified in `core/domain/models/config_schema.py` and `yaml_config_adapter.py`).
- The greenfield create path already feeds full untruncated content to the parser, so passing full content via `read_raw_file` matches existing behavior (verified in `execution_orchestrator` create branch).
- No new UX flow, external system integration, or domain rule ambiguity requires prototyping. The approved display notice format is user-confirmed.

## Impact

1. `[NEW]` `config_schema.PlanConfig` — New frozen dataclass with `max_lines: int = 5000`.
2. `[EXPAND]` `config_schema.AppConfig` — Add `plan: PlanConfig = field(default_factory=PlanConfig)` alongside existing sub-configs.
3. `[EXPAND]` `TextualPlanReviewer.__init__` — Add optional `config_service: IConfigService | None = None`, defaulting to `None` so the two existing test construction sites stay valid.
4. `[EXPAND]` `ReviewerApp` — Add an optional `config_service: IConfigService | None = None` attribute, threaded from `TextualPlanReviewer`.
5. `[MIGRATE]` `registries/reviewer.py::tui_factory` — Resolve `IConfigService` from the container and pass it into `TextualPlanReviewer(...)`.
6. `[MIGRATE]` `textual_plan_reviewer_previews.view_plan_handler` — Switch from `read_file` to `read_raw_file`, truncate at `plan.max_lines` (read from `app.config_service.get_setting("plan.max_lines", 5000)` when present, else `5000`) with a plain `[Showing first N of M lines.]` notice.
7. `[MIGRATE]` `session_orchestrator._prepare_plan_parsing` and `_validate_plan_with_context` — Switch the plan read from `read_file` to `read_raw_file`.
8. `[MIGRATE]` `execution_orchestrator` plan resolution (line 249) — Switch to `read_raw_file`.
9. `[MIGRATE]` `session_lifecycle_manager` plan synthesis (line 400) — Switch to `read_raw_file`.
10. `[MIGRATE]` `session_service._is_preserved_turn` plan read (line 339) — Switch to `read_raw_file`.

No `[CONTRACT]` step: no obsolete contract or method is removed. `read_file` remains the truncating entry point for user READ actions.

## Deliverables

- [x] **Interface** - Add `PlanConfig` (`max_lines: int = 5000`) to `config_schema.py`; wire into `AppConfig` via `field(default_factory=...)`; add a `plan:` block with `max_lines: 5000` to the bundled default config at `src/teddy_executor/resources/config/config.yaml`; and add optional `config_service: IConfigService | None = None` to `TextualPlanReviewer.__init__` and the `ReviewerApp` attribute.
- [x] **Wiring** - Thread `IConfigService` through `registries/reviewer.py::tui_factory` into `TextualPlanReviewer` / `ReviewerApp`. Then `textual_plan_reviewer_previews.view_plan_handler` reads the plan via `read_raw_file`, truncates at `plan.max_lines` (from `app.config_service.get_setting("plan.max_lines", 5000)`, falling back to `5000` when the config handle is absent), and appends the hint-less plain notice `[Showing first N of M lines.]`. Thinnest end-to-end user-visible fix; drives the display-level acceptance test.
- [ ] **Core** - Switch all correctness plan reads to `read_raw_file`: `session_orchestrator._prepare_plan_parsing`, `session_orchestrator._validate_plan_with_context`, `execution_orchestrator` plan resolution, `session_lifecycle_manager` plan synthesis, `session_service._is_preserved_turn`. Resolves the resume write-back data-loss hazard and the `## Message`-beyond-1000 marker miss.

## Implementation Notes

- **Interface (config layer):** Added the frozen `PlanConfig(max_lines: int = 5000)` dataclass to `config_schema.py`, wired `plan: PlanConfig = field(default_factory=PlanConfig)` into `AppConfig`, and registered `_FieldSpec("plan.max_lines", "plan", "max_lines", int, minimum=1)` so the key is declared, typed, and range-checked (it auto-extends `_KNOWN_TOP_LEVEL`). `construct_app_config` now passes `plan=PlanConfig(**group_overrides.get("plan", {}))` explicitly, so a nested `plan` override survives construction rather than being silently dropped.
- **Interface (bundled config):** The bundled `src/teddy_executor/resources/config/config.yaml` declares a `plan:` block with `max_lines: 5000` and an explanatory comment, so the cap is visible and editable by users.
- **Interface (documentation):** `config_service.md` documents `plan.max_lines` (int, default 5000) in the configuration-keys table, keeping the drift test (documented ⊆ schema) and the `get_setting`-parity test green.
- **Interface (reviewer handles):** `TextualPlanReviewer.__init__` gained an optional `config_service: Optional[IConfigService] = None`, stored as `_config_service` and threaded into the `ReviewerApp` it constructs. `ReviewerApp.__init__` gained the matching optional `config_service` parameter, exposed as the public `config_service` attribute so the plan-view handler can read `plan.max_lines`. Both default to `None`, so every existing construction site stays valid.
- **Interface (tests):** Added default/override/zero-rejection coverage for `plan.max_lines` to `test_config_schema.py` (extending the existing capacity parametrization), a bundled-config contract test `test_bundled_config_plan_limits.py`, and `test_reviewer_config_service.py` asserting both reviewer classes accept and retain the injected handle (using `register_mock`, not bare `MagicMock`).
- **Verification:** 43 targeted tests pass; the full `make test` suite is green (2173 passed, 5 skipped).
- **Wiring (composition root):** `registries/reviewer.py::tui_factory` resolves `IConfigService` from the container and passes `config_service=container.resolve(IConfigService)` into `TextualPlanReviewer`, threading the handle through to the public `ReviewerApp.config_service` attribute added by the Interface deliverable.
- **Wiring (render helper):** Added the pure `render_plan_view(content, max_lines)` helper, which reuses the canonical `truncate_lines` head path with the hint-less `[Showing first N of M lines.]` notice. Content at or below the cap, empty content, and a non-positive cap are returned unchanged, and the notice never carries the READ-tool "Use the 'Lines' parameter" hint.
- **Wiring (cap resolver):** `_resolve_plan_max_lines(app)` returns `get_setting("plan.max_lines", DEFAULT_APP_CONFIG.plan.max_lines)` when the app carries a config handle, else the schema default (5000), so an absent handle degrades gracefully.
- **Wiring (handler):** `view_plan_handler` now reads via `read_raw_file`. When the plan exceeds the cap, it writes the rendered content to a persisted temp file and opens that read-only, because `launch_editor` ignores the passed content when `persistent_path` is a real non-empty file. When nothing is truncated, it opens the real plan file read-only in place, preserving the existing regression invariant. The temp file is tracked in `_log_preview_files` for deferred cleanup.
- **Wiring (tests):** Five pure `render_plan_view` cases in `test_plan_view_truncation.py`; the migrated `test_view_plan_regression.py` (asserts `read_raw_file` and long-plan truncation to a persisted temp with the notice); and the extended `test_reviewer_wiring.py` asserting the resolved reviewer carries an `IConfigService`. The no-plan-path robustness acceptance flow stays green.
- **Verification:** 10 targeted tests pass; the full `make test` suite is green (2179 passed, 5 skipped).
- **Wiring (lint exemption):** `test_view_plan_regression.py` builds a duck-typed fake app and intercepts the module-level `launch_editor`, which has no constructor-injection seam, so it reuses the `patch`/`MagicMock` pattern grandfathered for the sibling inbound test modules. Added a scoped `per-file-ignores` entry (`TID251`) in `pyproject.toml`, mirroring the existing `test_tui_editor_suspend_resume.py` and `test_console_ask_loop_wiring.py` exemptions.

## Verification

1. **TUI viewer truncation:**
   Create a plan file longer than `plan.max_lines` (e.g., 6000 lines) in a session directory.
   Open the plan via the TUI plan reviewer's view action.
   Confirm the editor shows the first `plan.max_lines` lines and a trailing `[Showing first N of M lines.]` notice, with no "Use the 'Lines' parameter" text.
2. **Correctness reads:**
   Create a plan file longer than 1000 lines whose `## Message` section falls after line 1000.
   Execute the plan and confirm the full plan is parsed (all actions executed).
   Verify the turn remains in `session.context` (message-turn preservation).
3. **Config override:**
   Set `plan.max_lines: 200` in `.teddy/config.yaml`.
   Open a 500-line plan in the viewer.
   Confirm the notice reports "Showing first 200 of 500 lines."
