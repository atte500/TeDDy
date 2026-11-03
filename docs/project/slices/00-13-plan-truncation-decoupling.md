# Slice: Plan Truncation Decoupling

- **Status:** Completed
- **Milestone:** N/A (ad-hoc, from Case File 76)
- **Depends On:** N/A
- **Specs:** N/A
- **Prototype:** N/A
- **Component Docs:** [SessionOrchestrator](/docs/architecture/core/services/session_orchestrator.md), [SessionService](/docs/architecture/core/services/session_service.md), [LocalFileSystemAdapter](/docs/architecture/adapters/outbound/local_file_system_adapter.md), [TextualPlanReviewer](/docs/architecture/adapters/inbound/textual_plan_reviewer.md)
- **Scope Slug:** `plan-truncation`

## Goal

Decouple plan-file truncation from the READ-tool `read.max_lines` cap with three outcomes: the TUI `v` viewer always opens the real, uncapped `plan.md`; correctness reads always see the full plan; and `plan.max_lines` caps only the plan content embedded in the LLM context window (`input.md`), with pruning token counts derived from that truncated content so budgets track real window impact.

## Context

- Case File 76 verifies the root cause: `LocalFileSystemAdapter.read_file` head-truncates at `read.max_lines` (default 1000) via `truncate_lines(content, max_lines=self.max_read_lines, direction="head", action_type="read")`, appending the READ-tool hint `[Content truncated: ... Use the 'Lines' parameter ...]`. Six plan-read call sites route through it, so long plans are truncated and hint-stamped wherever they are viewed, refined, parsed, resumed, or preserved.
- `IFileSystemManager.read_raw_file` exists on the port and returns full untruncated content. `read_files_in_vault` already uses it for context assembly, so bypassing the cap is an established pattern in the codebase.
- `truncate_lines(content, max_lines, direction="head", hint="")` supports hint-less truncation: when `hint` is empty and `action_type` is absent, no banner is emitted. A plain custom hint string can be passed through the `hint` parameter.
- `AppConfig` in `core/domain/models/config_schema.py` composes nested frozen dataclasses (`ReadConfig.max_lines = 1000`, `ExecuteConfig`, `EditConfig`, etc.) via `field(default_factory=...)`. `IConfigService.get_setting("plan.max_lines", default)` resolves dotted keys through the same mechanism.
- `session_orchestrator._prepare_plan_parsing` reads the plan via `read_file` only when `plan_content` is None. The greenfield create path already feeds the full `plan_content` string into the parser, so routing through `read_raw_file` matches established behavior rather than introducing a new performance surface.
- The reviewer is composed in `registries/reviewer.py::tui_factory`, which constructs `TextualPlanReviewer` from container-resolved ports. Neither `TextualPlanReviewer` nor its `ReviewerApp` currently carries a config handle, so the slice adds an optional `config_service: IConfigService | None = None` to both (defaulting to `None`) to keep existing `ReviewerApp(` and `TextualPlanReviewer(` test construction sites green.
- `read_raw_file` is implemented concretely on `LocalFileSystemAdapter` (line 301), not just declared on the port, so correctness reads are directly callable today.
- **Option A re-scope (2026-11-03, user decision):** The plan cap belongs in the LLM context window, not the TUI viewer. `v` always opens the real `plan.md`; `plan.max_lines` caps `plan.md` content at context-assembly time (`ContextService`). Because `ContextService._get_path_to_tokens` derives each `ContextItem.token_count` from the same `file_contents` map that `_format_content` embeds, capping `plan.md` in `file_contents` before both steps makes pruning (`SessionPruningService._apply_global_budget`) prune on truncated length, matching real window impact. The rule is truncate-first-then-count. Only `plan.md` is capped; the cap applies wherever a `plan.md` is embedded (turn context and session history alike).
- `ContextService` currently has no `IConfigService` handle; it gains an optional one (defaulting to `None`) to read `plan.max_lines`, mirroring the reviewer's optional-handle pattern so the many existing construction sites stay valid.

## Scenarios

> As a developer reviewing a long plan, I want `v` to open the real `plan.md` on disk in full so that I inspect and edit exactly what will run.

```gherkin
Given a plan file of any length
When I press 'v' in the TUI plan reviewer
Then the editor opens the real plan.md read-only
And no truncated temp copy is created
And no "Use the 'Lines' parameter" hint is shown
```

> As a maintainer, I want a gigantic plan capped in the LLM context window so a rambling plan cannot dominate the token budget, while pruning counts what actually lands in the window.

```gherkin
Given a prior-turn plan.md longer than plan.max_lines embedded in context
When the context payload (input.md) is assembled
Then the embedded plan content is capped at plan.max_lines
And the plan item's token_count reflects the capped content
And pruning uses that capped length to decide what to drop
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

- **At the cap:** A `plan.md` with exactly `plan.max_lines` lines is embedded unchanged, because `truncate_lines` preserves content at or below the cap.
- **Empty plan:** An empty `plan.md` embeds empty with no notice, because `truncate_lines` short-circuits on empty content.
- **Zero or negative cap:** If `plan.max_lines` is `<= 0`, content is embedded unchanged; the schema already rejects non-positive values, so this is defensive only.
- **Non-plan files are never capped:** Only paths ending in `plan.md` are capped; `report.md` and all other files embed in full.
- **No config handle:** If `ContextService` is constructed without a config service (existing test sites), `plan.max_lines` falls back to the schema default (5000).
- **Config default:** `plan.max_lines` defaults to `5000` when absent from config, so existing workspaces require no migration.
- **Marker detection:** `_is_preserved_turn` searches full plan content for `## Message`, so a plan whose `## Message` falls beyond the old 1000-line cap is now correctly preserved.

## Key Unknowns

None. Every technical question was resolved during Discovery:
- `read_raw_file` exists on `IFileSystemManager` (verified in `core/ports/outbound/file_system_manager.py`).
- `truncate_lines` supports hint-less truncation (verified in `core/utils/string.py`).
- Config schema uses nested frozen dataclasses resolvable via `IConfigService.get_setting` (verified in `core/domain/models/config_schema.py` and `yaml_config_adapter.py`).
- The greenfield create path already feeds full untruncated content to the parser, so passing full content via `read_raw_file` matches existing behavior (verified in `execution_orchestrator` create branch).
- No new UX flow, external system integration, or domain rule ambiguity requires prototyping. The approved display notice format is user-confirmed.

## Impact

1. `[NEW]` `config_schema.PlanConfig` — frozen dataclass `max_lines: int = 5000` (shipped).
2. `[EXPAND]` `config_schema.AppConfig` — `plan: PlanConfig` sub-config (shipped).
3. `[EXPAND]` `TextualPlanReviewer` / `ReviewerApp` — optional `config_service` handle (shipped; retained harmlessly, though the viewer no longer reads `plan.max_lines`).
4. `[MIGRATE]` `textual_plan_reviewer_previews.view_plan_handler` — **revert display truncation**: always open the real `plan.md` read-only via `read_raw_file`; remove the temp-copy truncation branch.
5. `[MIGRATE]` `session_orchestrator._prepare_plan_parsing` and `_validate_plan_with_context` — correctness reads via `read_raw_file` (Core).
6. `[MIGRATE]` `execution_orchestrator._resolve_plan` — correctness read via `read_raw_file` (Core).
7. `[MIGRATE]` `session_lifecycle_manager._parse_awaiting_plan` — correctness read via `read_raw_file` (Core).
8. `[MIGRATE]` `session_service._is_preserved_turn` — correctness plan read via `read_raw_file` (Core).
9. `[EXPAND]` `ContextService` — add optional `config_service: IConfigService | None = None`; after `read_files_in_vault`, cap `plan.md` content in `file_contents` at `plan.max_lines` (truncate-first, so both the embed and `_get_path_to_tokens` see capped content).
10. `[MIGRATE]` `container.py` — pass `IConfigService` into the `ContextService` factory.
11. `[MIGRATE]` bundled `config.yaml` comment — reword the `plan.max_lines` comment from "Caps plan display lines in the TUI viewer." to "Caps plan lines included in the LLM context window."

`read_file` remains the truncating entry point for user READ actions; no contract is removed.

## Deliverables

- [x] **Interface** - Add `PlanConfig` (`max_lines: int = 5000`) to `config_schema.py`; wire into `AppConfig` via `field(default_factory=...)`; add a `plan:` block with `max_lines: 5000` to the bundled default config at `src/teddy_executor/resources/config/config.yaml`; and add optional `config_service: IConfigService | None = None` to `TextualPlanReviewer.__init__` and the `ReviewerApp` attribute.
- [x] **Wiring** - Thread `IConfigService` through `registries/reviewer.py::tui_factory` into `TextualPlanReviewer` / `ReviewerApp`, and (originally) truncate the viewer. Option A re-scope: the viewer-truncation half is superseded by the Cleanup deliverable below; the config-threading half stays.
- [x] **Core** - Switch all correctness plan reads to `read_raw_file`: `session_orchestrator._prepare_plan_parsing`, `session_orchestrator._validate_plan_with_context`, `execution_orchestrator` plan resolution, `session_lifecycle_manager` plan synthesis, `session_service._is_preserved_turn`. Resolves the resume write-back data-loss hazard and the `## Message`-beyond-1000 marker miss.
- [x] **Adapter** - `ContextService` gains an optional `IConfigService` and caps `plan.md` content in `file_contents` at `plan.max_lines` at context-embed time (truncate-first, so the embedded window AND the pruning `token_count` reflect the cap). Container wires the handle. Integration tests drive a real context assembly with a long prior-turn plan.
- [x] **Cleanup** - Revert the TUI viewer to always open the real `plan.md`: remove `render_plan_view`, `_resolve_plan_max_lines`, and their display-truncation tests. (The bundled `config.yaml` `plan.max_lines` comment was already reworded in the Adapter deliverable.)

## Implementation Notes

- **Interface (config layer):** Added the frozen `PlanConfig(max_lines: int = 5000)` dataclass to `config_schema.py`, wired `plan: PlanConfig = field(default_factory=PlanConfig)` into `AppConfig`, and registered `_FieldSpec("plan.max_lines", "plan", "max_lines", int, minimum=1)` so the key is declared, typed, and range-checked (it auto-extends `_KNOWN_TOP_LEVEL`). `construct_app_config` now passes `plan=PlanConfig(**group_overrides.get("plan", {}))` explicitly, so a nested `plan` override survives construction rather than being silently dropped.
- **Interface (bundled config):** The bundled `src/teddy_executor/resources/config/config.yaml` declares a `plan:` block with `max_lines: 5000` and an explanatory comment, so the cap is visible and editable by users.
- **Interface (documentation):** `config_service.md` documents `plan.max_lines` (int, default 5000) in the configuration-keys table, keeping the drift test (documented ⊆ schema) and the `get_setting`-parity test green.
- **Interface (reviewer handles):** `TextualPlanReviewer.__init__` gained an optional `config_service: Optional[IConfigService] = None`, stored as `_config_service` and threaded into the `ReviewerApp` it constructs. `ReviewerApp.__init__` gained the matching optional `config_service` parameter, exposed as the public `config_service` attribute so the plan-view handler can read `plan.max_lines`. Both default to `None`, so every existing construction site stays valid.
- **Interface (tests):** Added default/override/zero-rejection coverage for `plan.max_lines` to `test_config_schema.py` (extending the existing capacity parametrization), a bundled-config contract test `test_bundled_config_plan_limits.py`, and `test_reviewer_config_service.py` asserting both reviewer classes accept and retain the injected handle (using `register_mock`, not bare `MagicMock`).
- **Verification:** 43 targeted tests pass; the full `make test` suite is green (2173 passed, 5 skipped).
- **Wiring (composition root):** `registries/reviewer.py::tui_factory` resolves `IConfigService` from the container and passes `config_service=container.resolve(IConfigService)` into `TextualPlanReviewer`, threading the handle through to the public `ReviewerApp.config_service` attribute added by the Interface deliverable.
- **Wiring (viewer display, superseded):** The Wiring deliverable originally added a pure `render_plan_view` helper, a reviewer-side `_resolve_plan_max_lines`, and a `view_plan_handler` branch that rendered a truncated temp copy with the hint-less `[Showing first N of M lines.]` notice. Option A moved the cap to the context window, so the Cleanup deliverable removed all of this: the viewer now always opens the real `plan.md`, and the hint-less cap lives in `ContextService._cap_plan_content`. `test_reviewer_wiring.py` (reviewer carries an `IConfigService`) and the no-plan-path robustness flow stay green.
- **Verification:** 10 targeted tests pass; the full `make test` suite is green (2179 passed, 5 skipped).
- **Wiring (lint exemption):** `test_view_plan_regression.py` builds a duck-typed fake app and intercepts the module-level `launch_editor`, which has no constructor-injection seam, so it reuses the `patch`/`MagicMock` pattern grandfathered for the sibling inbound test modules. Added a scoped `per-file-ignores` entry (`TID251`) in `pyproject.toml`, mirroring the existing `test_tui_editor_suspend_resume.py` and `test_console_ask_loop_wiring.py` exemptions.

- **Option A re-scope (2026-11-03):** The user redirected the plan cap from the TUI viewer to the LLM context window. The Adapter (context cap) and Cleanup (viewer revert) deliverables implement this; correctness reads (Core) are unaffected and remain required. Pruning needs no separate change: capping `plan.md` in `file_contents` before `_get_path_to_tokens` makes `token_count` — and therefore `_apply_global_budget` — track the truncated length, which matches real window impact.

- **Core (correctness reads):** Switched all five correctness plan reads to `read_raw_file`, so parsing, validation-error surfacing, execution, resume synthesis, and turn-preservation always consume the full plan: `session_orchestrator._prepare_plan_parsing` and `_validate_plan_with_context`, `execution_orchestrator._resolve_plan`, `session_lifecycle_manager._parse_awaiting_plan`, and `session_service._is_preserved_turn`. This eliminates the resume/execute write-back data-loss hazard (parsing no longer sees the READ-capped view) and the `## Message`-beyond-1000 marker miss. `read_file` stays the truncating entry point for user READ actions and for the report/user-request reads that remain on it.
- **Core (tests):** Added `test_is_preserved_turn_full_plan.py`, which proves Red the marker miss via the real `LocalFileSystemAdapter` at `max_read_lines=1000`, then goes Green after the `_is_preserved_turn` swap. Migrated two fixtures to the new read path: the bespoke `InMemoryFileSystem` fake in `test_session_lifecycle_resume_message_persistence.py` gained `read_raw_file` (mirrors `read_file` because it stores full content), and `test_session_orchestrator.py::...trigger_replan...` pins `"plan content"` on `read_raw_file` at the swapped site.
- **Verification:** Full `make test` green (2180 passed, 5 skipped).

- **Adapter (context-window cap):** `ContextService` gained an optional `config_service: IConfigService | None = None`. Immediately after `read_files_in_vault` builds `file_contents`, `_cap_plan_contents` truncates any `plan.md` entry at `plan.max_lines` (default 5000) before both `_format_content` (the embedded `input.md` text) and `_collect_items`→`_get_path_to_tokens` (the per-item `token_count`). Truncate-first means the pruning `token_count` tracks the capped length, so `SessionPruningService._apply_global_budget` prunes on real window impact. Only paths ending in `plan.md` are capped; `report.md` and all other files embed verbatim, and a not-found (`None`) entry passes through. The cap reuses the canonical hint-less `[Showing first N of M lines.]` notice, and `_resolve_plan_max_lines` falls back to `DEFAULT_APP_CONFIG.plan.max_lines` when no config handle is present.
- **Adapter (container):** `container.py` passes `config_service=container.resolve(IConfigService)` into the `ContextService` factory.
- **Adapter (tests):** `test_context_plan_cap.py` drives a real `LocalFileSystemAdapter` over an isolated tmp workspace with constructor-injected config/LLM fakes, proving the embedded plan caps at `plan.max_lines`, the item `token_count` sits strictly below the full-file count, the on-disk `plan.md` stays full, and `report.md` is never capped.
- **Adapter (config comment):** Reworded the bundled `config.yaml` `plan.max_lines` comment from "Caps plan display lines in the TUI viewer." to "Caps plan lines included in the LLM context window.", reflecting that the cap applies to context assembly, not the viewer.
- **Verification:** Full `make test` green (2183 passed, 5 skipped).

- **Cleanup (viewer revert):** `view_plan_handler` now always opens the real `plan.md` read-only in place via `read_raw_file`; the temp-copy display-truncation branch is gone. Removed `render_plan_view` and the reviewer-side `_resolve_plan_max_lines`, plus the now-unused `DEFAULT_APP_CONFIG` and `truncate_lines` imports from the previews module. When a plan has no on-disk path (e.g. `--plan-content`), `launch_editor` still opens a temp copy carrying the content, because `persistent_path` is then `None`.
- **Cleanup (tests):** Deleted `test_plan_view_truncation.py` (all five cases pinned the removed helper) and rewrote the long-plan case in `test_view_plan_regression.py` to assert the plan opens in full at the real path with no truncation notice. The reviewer `config_service` handle and `test_reviewer_config_service.py` are retained (Impact #3: harmless).
- **Verification:** Full `make test` green (2178 passed, 5 skipped).

## Verification

1. **Viewer opens the real plan:**
   Create a plan file longer than `plan.max_lines` (e.g., 6000 lines) in a session directory.
   Press 'v' in the TUI plan reviewer.
   Confirm the editor opens the real `plan.md` in full (no truncation notice, no "Use the 'Lines' parameter" text, and the on-disk file is what is opened).
2. **Context-window cap:**
   Set `plan.max_lines: 200` in `.teddy/config.yaml`; start a turn whose context embeds a 500-line prior `plan.md`.
   Inspect `input.md` and confirm the embedded plan is capped at 200 lines, while the on-disk `plan.md` remains 500 lines.
3. **Pruning tracks capped length:**
   With a small `auto_pruning.turn_context_threshold`, confirm the plan item's token count reflects the capped content (a huge plan no longer alone blows the budget).
4. **Correctness reads:**
   Create a plan file longer than 1000 lines whose `## Message` section falls after line 1000.
   Execute the plan and confirm the full plan is parsed (all actions executed) and the turn remains in `session.context` (message-turn preservation).
