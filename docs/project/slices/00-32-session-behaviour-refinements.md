# Slice: Session Behaviour Refinements (Init, Prompts/Templates, Config Checks & Agent Casing)
- **Status:** In Progress
- **Milestone:** N/A
- **Specs:** N/A
- **Prototype:** N/A
- **Component Docs:** [InitService](/docs/architecture/core/services/init_service.md), [SessionService](/docs/architecture/core/services/session_service.md), [PromptManager](/docs/architecture/core/services/prompt_manager.md)
- **Scope Slug:** `session-behaviour`

## Business Goal

Deliver six coordinated refinements so that (a) templates are scaffolded only on explicit request, (b) the session audit trail records the exact composed system prompt the model receives and then reuses it, (c) drift between user prompts/templates and bundled defaults is surfaced with an actionable notification (independently switchable), and (d) the agent name is displayed and persisted in canonical casing regardless of CLI input.

## Scenarios

> As a user, I want `docs/templates/` to be created only when I explicitly ask for it.

```gherkin
Feature: Explicit-only template initialization
  Scenario: Bare init and start do not scaffold templates
    Given a project with no docs/templates/ directory
    When the user runs `teddy init`
    Then docs/templates/ is NOT created
    When the user runs `teddy start`
    Then docs/templates/ is still NOT created

  Scenario: Explicit init templates scaffolds templates
    Given a project with no docs/templates/ directory
    When the user runs `teddy init templates`
    Then docs/templates/ contains all bundled templates
```

> As a user, I want the session folder to contain the exact system prompt sent to the model.

```gherkin
Feature: Composed system prompt persisted and reused
  Scenario: Composition on creation
    Given the user runs `teddy start -a pathfinder`
    When the session is created
    Then .teddy/sessions/<session>/pathfinder.xml starts with "Agent Name: Pathfinder"
    And it contains the agent XML followed by the MRP base prompt

  Scenario: Reuse on later turns
    Given an existing composed session prompt
    When the next turn requests the system prompt
    Then the persisted composed prompt is returned verbatim (no re-composition)

  Scenario: Recompose on agent switch
    Given an existing session
    When the user runs `teddy resume -a developer`
    Then the session-root prompt file is recomposed for developer
    And stale prompt files for other agents are removed
```

> As a user, I want a warning when my prompts/templates drift from the bundled defaults.

```gherkin
Feature: Prompt and template drift notification
  Scenario: Edited prompt
    Given .teddy/prompts/pathfinder.xml differs from the bundled default
    When the user runs `teddy start`
    Then a yellow message advises running `teddy init prompts`

  Scenario: Missing template
    Given a file in docs/templates/ is missing
    When the user runs `teddy start`
    Then a yellow message advises running `teddy init templates`
```

> As a user, I want to disable the checks independently.

```gherkin
Feature: Independent check toggles
  Scenario: Prompts/templates check disabled
    Given config.yaml disables the prompts/templates check
    When the user runs `teddy start`
    Then no prompt/template drift message is emitted

  Scenario: Update check disabled
    Given config.yaml disables the update check
    When a newer version is available in the cache
    Then no update notification is emitted
```

> As a user, I want canonical agent casing regardless of how I type the agent.

```gherkin
Feature: Agent name canonical casing
  Scenario: Uppercase input
    Given the user runs `teddy start -a PATHFINDER`
    Then the banner shows "Agent: Pathfinder"
    And the planning header shows "Waiting for Pathfinder to respond..."
    And meta.yaml stores agent_name: Pathfinder
```

## Edge Cases

- **No prompts directory**: If `.teddy/prompts/` is absent, the drift check reports prompts as missing and the notification still fires; resolution continues to raise the existing "run `teddy init`" error only when a session is actually created.
- **Legacy `<response_format>` override**: A resolved prompt carrying its own `<response_format>` is returned with the agent-name header but WITHOUT the appended MRP (existing behaviour preserved).
- **Case-insensitive resolution unchanged**: Resolution stays casefold-insensitive; only display/persistence canonicalises.
- **Toggle absent from config**: Defaults to enabled, so existing user configs are unaffected (backwards compatible).
- **Unknown agent on recompose**: `teddy resume -a <unknown>` fails with the existing "Available agents" error rather than writing a prompt.
- **First run with no cache**: The update-check toggle must not suppress the background fetch itself — only the user-facing notification — so caching continues.
- **Composed-vs-raw ambiguity**: A raw session-root override that happens to open with `Agent Name:` must not be mistaken for a composed prompt (see Key Unknowns).

## Key Unknowns

- [x] [Functional] Where to emit the drift notification? Resolved: `teddy start`/`resume` preflight, adjacent to the update check.
- [x] [Technical] Where to persist the composed prompt? Resolved: the session root (`{session}/<agent>.xml`), reused verbatim on later turns.
- [x] [Technical] How to distinguish a persisted composed prompt from a raw override at the session root (to prevent the double-composition trap)? Resolved (Option A — no detection needed): split the compose role from the read role. Compose the full system prompt at session creation and on agent switch, persist it, then have `fetch_system_prompt` return the persisted file verbatim — so no content inspection is ever required. A MISSING file lazily recomposes from `.teddy/prompts/` and writes it (a safe fallback, not a heuristic).

## Implementation Plan

### Item 1 — Templates explicit-only
Remove the `_init_templates(overwrite=False)` call (and the trailing `Templates:` summary segment) from `InitService.ensure_initialized()`, so `docs/templates/` is written only by `ensure_templates_initialized()` (the `teddy init templates` path). This REVERSES a decision recorded in the completed slice [`03-03-templates-and-init`](/docs/project/slices/03-03-templates-and-init.md). The reversal of the acceptance contract lives in Item 1: rewrite `tests/suites/acceptance/test_templates_auto_init.py` to assert that bare `teddy init` does NOT create `docs/templates/`, and update the two `Templates:` summary assertions in `tests/suites/unit/core/services/test_init_service.py`. The `03-03` slice doc is updated separately by the Cleanup deliverable.

### Item 2 — Compose once → persist → read verbatim (Option A, per user decision)
Split the current dual role of `PromptManager.fetch_system_prompt` (which both composes AND reads) into a distinct compose step and read step:

- **Compose (at `SessionService.create_session` and on agent switch):** assemble the full system prompt — `Agent Name: <canonical>` header + agent XML (resolved from `.teddy/prompts/`) + appended `MRP.xml` — and persist it to `{session_root}/{prompt_filename}`. Reuse the existing assembly logic in `PromptManager.fetch_system_prompt(agent, turn_path)` to build the string, then write the result.
- **Read (`PromptManager.fetch_system_prompt`, every turn):** return the persisted `{session_root}/{prompt_filename}` **verbatim** — no header prepend, no MRP append, no content sniffing. Because the session-root file *is by definition* the composed prompt, no composed-vs-raw disambiguation is required (this is why the Key Unknown above is now resolved).
- **Lazy-compose fallback:** if the session-root file is MISSING (legacy session or manual delete), compose from `.teddy/prompts/`, persist it, then return it.
- **Recompose on agent switch:** the existing `teddy resume -a <agent>` path (`SessionService.set_session_agent`) recomposes the prompt for the new agent and removes stale agent prompt files.

The legacy `<response_format>` early-return (skip the MRP append when a resolved prompt already carries its own response format) moves INTO the compose step so the reader stays trivial.

### Items 3/4 — Prompt/template drift detection
Introduce a drift-check capability that compares each `.teddy/prompts/*.xml` and each `docs/templates/*.md` against its bundled default and reports edited and missing entries. Emit the aggregated result at the `teddy start`/`resume` preflight as a yellow message naming the actionable command (`teddy init prompts` / `teddy init templates`). Reuse the `typer.echo(typer.style(..., fg=typer.colors.YELLOW))` convention already used by `_display_update_notification`.

### Item 5 — Independent config toggles
Add independent toggle keys to the bundled `config.yaml` (read via `IConfigService.get_setting`; ADDITIVE, no port signature change). Gate the drift notification and the update notification behind their respective toggles, defaulting to enabled when absent.

**Locked key names (fixed by the Developer at Phase 1 Plan Audit):** a single `checks:` block with `checks.prompts_templates` (gates the prompts/templates drift notification) and `checks.update` (gates the update notification). Both default to `true` when absent, so existing user configs are unaffected (backwards compatible). The `checks.update` toggle gates the user-facing NOTIFICATION only — the background version fetch/caching still runs.

### Item 6 — Canonical agent casing
Add a single canonical-casing helper (agent name → the resolved prompt file stem, `.capitalize()`). Apply it at (a) the `_echo_config_success` banner interpolation, and (b) `SessionService` meta persistence (`_initialize_meta_data`, `set_session_agent`). Because `planning_service.py` reads `meta["agent_name"]`, canonicalising the persisted value fixes the `Waiting for … to respond...` header automatically.

### Impact Notes (Phase 4 audit)
- `IConfigService` — many consumers, but the change is additive (`get_setting`); NO signature change → no Contract→Migration→Cleanup partitioning.
- `IPromptManager.fetch_system_prompt` — consumers are `planning_service` (60) and `session_orchestrator` (435); signature unchanged, behaviour backward compatible → no partitioning, but both consumers must be covered by tests.
- `SessionOptions` DTO — unchanged.
- `IInitUseCase` — unchanged interface (only `ensure_initialized` internals change).

## Deliverables

- [x] **Logic** — Item 1: drop the `_init_templates` call (and the trailing `Templates:` summary segment) from `InitService.ensure_initialized`; reverse the acceptance contract in `tests/suites/acceptance/test_templates_auto_init.py` and update the two summary-string assertions in `tests/suites/unit/core/services/test_init_service.py` in the same change set.
- [x] **Logic** — Item 2: compose+persist in `SessionService.create_session`; verbatim reuse in `PromptManager.fetch_system_prompt`; recompose in `set_session_agent`.
- [x] **Logic** — Item 6: canonicalise agent casing in `_echo_config_success` and meta persistence.
- [x] **Contract** — Item 5: add the two config toggle keys to the bundled `config.yaml` (additive; read via `IConfigService.get_setting`).
- [x] **Seam** — Items 3/4: a drift-check helper comparing user files against bundled defaults.
- [x] **Wiring** — Items 3/4/5: emit the drift notification at the start/resume preflight and gate it (plus the update notification) by the toggles.
- [x] **Harness** — Regression/unit tests for the drift checker and its toggle gating; add an acceptance test for the (toggle-gated) drift notification.
- [x] **Refactor** — Single-source the canonical-casing helper (avoid duplicating the stem→`capitalize()` logic).
- [x] **Cleanup** — Update the `03-03-templates-and-init` slice doc to record the reversed explicit-only contract; remove `spikes/debug/` if present.

## Implementation Notes

### Item 1 — Templates explicit-only (complete)

**Production change.** `InitService.ensure_initialized()` no longer calls `_init_templates(overwrite=False)` and no longer appends a `Templates:` segment to its summary; it now returns `f"Config: {config_status}. Prompts: {prompts_status}."`, and its docstring documents the explicit-only contract. The explicit `teddy init templates` path (`ensure_templates_initialized` → `_init_templates`) is untouched and stays GREEN. This reverses the completed decision recorded in slice `03-03-templates-and-init` (whose doc is updated separately by the Cleanup deliverable).

**Contract reversal — the blast radius was THREE test files, not two.** The Plan Audit identified two coupling sites, but the Phase 3 full-suite gate surfaced a third:
- `tests/suites/acceptance/test_templates_auto_init.py` — reversed to assert that bare `teddy init` does NOT create `docs/templates/` (renamed test `test_bare_teddy_init_does_not_scaffold_docs_templates`).
- `tests/suites/unit/core/services/test_init_service.py` — the two `ensure_initialized` summary assertions dropped the `Templates:` segment (`"Config: unchanged. Prompts: unchanged."` and `"Config: updated (4 files). Prompts: updated (6 files)."`).
- `tests/suites/unit/adapters/inbound/test_cli_init_command_isolation.py` — the CWD-confinement guard asserted `(workspace / "docs" / "templates").is_dir()`, which the Item 1 change invalidated. Classified as a **Local Flaw** (Phase 3 Step 2): the fix required editing ONLY this existing test file, no out-of-scope production change. Its meaningful `.teddy/` confinement guards were preserved; the now-vacuous `docs/templates` assertion and the parent-`docs/` assertion (bare init no longer creates `docs/`) were removed, and the docstring was refreshed.

**Blast-radius lesson.** The missed coupling expressed the path as SEPARATE components (`tmp_path / "docs" / "templates"`), so a literal `git grep "docs/templates"` did not flag it. Future audits of path-coupling reversals MUST also sweep the path TAIL component (e.g. `git grep '"templates"'`).

**Verification.** Red (Turn 8): `3 failed, 17 passed`. Green (Turn 9): targeted run `21 passed`. Phase 3 (Turn 13): full suite `1683 passed, 5 skipped`.

### Item 2 — Composed system prompt persisted and reused (Option A, complete)

**Production change.** Split the dual compose+read role of `PromptManager.fetch_system_prompt` into distinct steps:

- **Compose+persist at session creation.** `SessionService.create_session` resolves the target filename via `_resolve_agent_prompt` (which retains its agent-validation `ValueError` and its case-preserving filename role) and obtains the COMPOSED system prompt by calling `self._prompt_manager.fetch_system_prompt(options.agent_name, Path(turn_dir))`. Because the session root is still empty at that point, the reader takes its lazy-compose path (`.teddy/prompts/` → `Agent Name: <Canonical>` header + agent XML + appended `MRP.xml`), and the composed string is persisted to `{session_root}/{prompt_filename}` via the service's own `IFileSystemManager`.
- **Recompose+persist on agent switch.** `SessionService.set_session_agent` mirrors the same shape: it resolves the filename via `_resolve_agent_prompt`, calls `fetch_system_prompt(agent_name, Path(latest_turn_path))` for the new agent, persists the composed value, and keeps its stale-stem pruning.
- **Verbatim read every turn.** `PromptManager.fetch_system_prompt` returns the persisted session-root file UNCHANGED — no header prepend, no MRP append, no content sniffing. Because the session-root file IS by definition the composed prompt, no composed-vs-raw disambiguation is required (Key Unknown resolved). `_resolve_agent_prompt_content` was retargeted to read only canonically from `.teddy/prompts/`; the legacy `<response_format>` skip moved INTO the compose step so the reader stays trivial.

**Three Red-Green cycles.** Green 1 (`test_prompt_manager.py::test_fetch_system_prompt_returns_persisted_composed_prompt_verbatim`, Turn 22→23 → `12 passed`) established the verbatim reader and the `.teddy/prompts/`-only resolver. Green 2 (`test_session_service.py::test_create_session_persists_composed_prompt_at_session_root`, Turn 25→27 → `1 passed`) landed compose+persist in `create_session`. Green 3 (`test_session_service_pruning.py::test_set_session_agent_persists_recomposed_prompt_at_session_root`, Turn 29→31 → `1 passed`) landed recompose+persist in `set_session_agent`. All three failed first with the exact `write_file(..., composed) call not found` smoking gun, confirming the compose contract was genuinely unimplemented (not coincidentally passing).

**Phase 3 Local Recovery.** The Global Run (Turn 32) surfaced `5 failed, 1681 passed, 5 skipped` — all five in the deliverable's in-scope test files, so classified LOCAL FLAWS (no Systemic Regression; no abort/re-plan). Each stale test pinned the OLD raw `.teddy/prompts/` content; each was re-pointed at the composed contract WITHOUT weakening its original intent (path placement, meta updates, stale-stem pruning, `.teddy/prompts/` read). The five repaired tests: `test_session_service.py::{test_create_session_orchestrates_filesystem_correctly, test_create_session_reads_prompt_from_teddy_prompts, test_set_session_agent_updates_meta_yaml_and_copies_prompt, test_set_session_agent_removes_stale_prompt_files}` and `test_session_service_pruning.py::test_create_session_does_not_put_prompt_in_turn_directory`. Tests lacking an explicit `IPromptManager` mock gained a deterministic `env.mock_port(IPromptManager)` so the composed value is asserted regardless of the env default binding. `test_session_service_dynamic_agent_naming.py` asserts prompt PATHS only, so it stayed GREEN (no edit).

**Verification.** Red 1 (Turn 22): verbatim-read test failed on doubled header + MRP. Red 2 (Turn 25): `write_file(..., composed) call not found`. Red 3 (Turn 29): `write_file(..., composed) call not found`. Green 1 (Turn 23): `test_prompt_manager.py` → `12 passed`. Green 2 (Turn 27): targeted → `1 passed`. Green 3 (Turn 31): targeted → `1 passed`. Phase 3 (Turn 35): full suite `1686 passed, 5 skipped in 9.24s` (exit 0).

### Item 6 — Canonical agent casing (complete)

**Production change.** A single canonical-casing helper `canonical_agent_name(agent)` (returning `agent.capitalize()`) was added to `src/teddy_executor/core/utils/string.py`. It is applied at three seams so `-a PATHFINDER`, `-a pathfinder` and `-a DeVeLoPeR` display/persist identically as `Pathfinder` / `Developer`:

- **CLI banner** (`session_cli_handlers._echo_config_success`): the import was co-located with the existing `slugify` import, and the banner interpolation became `msg += f" | Agent: {canonical_agent_name(agent)}"` INSIDE the existing `if agent:` None-guard (required because `handle_plan_generation` calls `_echo_config_success(container)` with no `agent`).
- **Initial turn metadata** (`SessionService._initialize_meta_data`): `"agent_name": canonical_agent_name(options.agent_name)`.
- **Agent switch** (`SessionService.set_session_agent`): `meta["agent_name"] = canonical_agent_name(agent_name)`.

Because `planning_service.py` reads `meta["agent_name"]` directly, canonicalising the PERSISTED value fixes the `Waiting for <Agent> to respond...` planning header automatically — no planning-service edit was needed. Case-insensitive RESOLUTION is preserved: the raw `agent_name` still drives `_resolve_agent_prompt` / `fetch_system_prompt` (casefold), so only DISPLAY/persistence canonicalises. The carried-forward `agent_name` in `_persist_next_meta` (`current_meta.get("agent_name", "pf")`) is canonical automatically (inherited from the two source seams), so no edit was warranted.

**Three Red-Green cycles.** Green 1 (`test_string_utils.py::test_canonical_agent_name_standardizes_agent_slug_casing`, Turn 43→44 → `16 passed`) introduced the helper. Green 2 (`test_echo_config_success_agent_casing.py`, Turn 46→48 → `3 passed`) applied it at the CLI banner. Green 3 (`test_session_service_agent_casing.py`, Turn 50→52 → `6 passed`) applied it at both meta write sites. Every Red step failed first on the canonical-form assertion (banner: `Expected canonical 'Agent: Pathfinder' ... got '... | Agent: PATHFINDER'`; meta: `meta.yaml must persist the canonical agent name, got 'pathfinder'`), confirming the contract was genuinely unimplemented rather than coincidentally passing.

**Phase 3 Local Recovery.** The Global Run (Turn 54) surfaced `2 failed, 1694 passed, 5 skipped` — both in-scope TEST files, so classified LOCAL FLAWS (no Systemic Regression; no abort/re-plan). Each stale assertion pinned the pre-change RAW casing; each was re-pointed at the canonical contract without weakening intent: `test_bug_16_model_override_message.py` (`assert "pathfinder" in output` → `assert "Pathfinder" in output`) and `test_session_service.py` (`{"agent_name": "developer", ...}` → `{"agent_name": "Developer", ...}`). No production widening.

**Verification.** Red 1 (Turn 43): canonical-form unit test fails. Red 2 (Turn 46): `3 failed` on banner casing. Red 3 (Turn 50): `6 failed` on meta casing. Green 1 (Turn 44): `test_string_utils.py` → `16 passed`. Green 2 (Turn 48): banner suite → `3 passed`. Green 3 (Turn 52): meta suite → `6 passed`. Phase 3 (Turn 55): full suite `1696 passed, 5 skipped in 10.17s` (exit 0).

### Item 5 — Independent config toggles (complete)

**Production change.** The bundled `src/teddy_executor/resources/config/config.yaml` gained ONE additive top-level `checks:` mapping, inserted immediately after the `research:` block:

    checks:
      prompts_templates: true # Notify when docs/templates/ has drifted from the bundled defaults.
      update: true # Notify when a newer TeDDy version is available (background fetch still runs).

The change is strictly additive (a brand-new top-level key), so `YamlConfigAdapter` and every existing `get_setting` read are untouched — NO `IConfigService` signature change, hence no Shared-Seam partitioning. Both toggles default to enabled; the downstream Wiring deliverable reads them via `get_setting("checks.prompts_templates", True)` / `get_setting("checks.update", True)`, so existing user configs that lack the `checks` block behave as enabled (backwards compatible). The `checks.update` toggle gates the user-facing NOTIFICATION only — the background version fetch/caching still runs.

**One Red-Green cycle.** Red (Turn 64): `tests/suites/unit/test_bundled_config_notification_toggles.py` was created — a unit-layer Contract test that reads the bundled `config.yaml` via `resources.files("teddy_executor.resources.config").joinpath("config.yaml").read_text(encoding="utf-8")` (mirroring the `test_prompt_resource_relocation.py` package-resource precedent). The single-file run failed `1 failed` with `AssertionError: Bundled config.yaml must declare a 'checks' mapping for notification toggles, got: None` — the exact missing condition. Green (Turn 65): the additive `checks:` block was inserted; the single-file run returned `1 passed`. Refactor (Phase 2 Step 3) was a no-op — a minimal additive config block introducing no duplication, magic numbers, shadow logic, dead code, or DI impurity — so no `[DEBT]` was logged.

**Phase 3 Integration.** The full suite (`make test`, no filters) ran GREEN at `1697 passed, 5 skipped in 9.37s` — the prior `1696` baseline plus the one new toggle-contract test — confirming the additive change is Green-to-Green with no regression. No Phase 3 recovery was required.

### Seam Items 3/4 — Prompt/template drift detection (complete)

**Production change.** A new immutable domain model `DriftReport` (`src/teddy_executor/core/domain/models/drift_report.py`) carries four basename tuples (`edited_prompts`, `missing_prompts`, `edited_templates`, `missing_templates`) plus `has_drift` / `prompts_drifted` / `templates_drifted` convenience properties for the downstream Wiring. `IInitUseCase` gained ONE additive abstract member, `check_drift() -> DriftReport` — a Shared-Seam ADDITION, not a breaking signature change (every port double is spec-based and auto-adapts; ZERO hand-written subclasses), so no Contract→Migration→Cleanup partition was required. `InitService.check_drift` reuses the EXISTING `_config_dir` / `_templates_dir` / `_get_default_content` / `_read_bundled_resource` seams via a new `_classify_drift` per-file helper (a file is MISSING when the user copy is absent; EDITED when it exists and differs from a resolvable bundled default; unresolvable defaults are skipped, never reported as drift). The inline prompt manifest was extracted into a module-level `_PROMPT_FILES` constant (mirroring `_TEMPLATE_FILES`), single-sourcing the copy routine (`_init_prompts`) and the drift check. Because the check enumerates the canonical preset, an absent `.teddy/prompts/` directory simply makes every prompt report as MISSING (per-file check, no directory special-casing).

**One Red-Green cycle.** Red (Turn 76): `tests/suites/unit/core/services/test_init_service_drift.py` was created — a unit-layer Seam test injecting a spec-based `IFileSystemManager`, building `InitService` through its existing `config_dir` / `templates_dir` seam, and arranging exactly one edited user prompt (`pathfinder.xml`) and one missing user template (`ci.md`) with all other files byte-identical to their bundled default. The single-file run failed `1 failed` with `AttributeError: 'InitService' object has no attribute 'check_drift'` — the exact missing condition, confirming the seam was genuinely unimplemented (not coincidentally passing). Green (Turn 77): the `DriftReport` model, the additive port member and the `check_drift` / `_classify_drift` implementation landed; the run returned `1 passed`. Refactor (Phase 2 Step 3) was folded into Green (`_PROMPT_FILES`), so it was a no-op — no duplication, magic numbers, shadow logic, dead code, or DI impurity remained, and no `[DEBT]` was newly logged.

**Phase 3 Integration.** The full suite (`make test`, no filters) ran GREEN at `1698 passed, 5 skipped` — the prior `1697` baseline plus the one new drift test — confirming the additive change is Green-to-Green with no regression. No Phase 3 recovery was required.

### Wiring Items 3/4/5 — Preflight drift notification + independent toggle gating (complete)

**Production change.** `src/teddy_executor/adapters/inbound/session_cli_handlers.py` gained a `_display_drift_notification(container)` helper (placed immediately before `_display_update_notification`) that resolves `IInitUseCase`, calls `check_drift()`, and — when `report.has_drift` — emits a yellow advice naming the actionable command (`teddy init prompts` / `teddy init templates`). The helper is invoked on the `_run_cli_preflight_check` HEALTHY path — the shared slot reached by `start`, `plan` and `resume` after `ensure_initialized()` — so a single wiring point covers every entry command. Both notification helpers are now gated by their INDEPENDENT config toggles: `_display_drift_notification` early-returns when `get_setting("checks.prompts_templates", True)` is falsy; `_display_update_notification` (signature widened from `(cache_path)` to `(container, cache_path)`) early-returns when `get_setting("checks.update", True)` is falsy, and `container` is threaded into BOTH of its call sites (`handle_new_session` start and `handle_resume_session` resume). The arity change is module-local (no external callers) → Green-to-Green. `IConfigService` was already imported, so no import churn was required. The `checks.update` gate suppresses only the user-facing NOTIFICATION; the background version fetch/caching still runs.

**Two Red-Green cycles.** Emit half — Red#1 (Turn 91): `tests/suites/acceptance/test_preflight_drift_notification.py` was authored as an acceptance tracer bullet (Subcutaneous Testing; imports only the harness) driving `teddy start` against a real-filesystem workspace whose `.teddy/prompts/pathfinder.xml` differs from the bundled default, expecting the yellow `teddy init prompts` advice. The single-file run failed `1 failed` with an `AssertionError` whose captured output contained no advice — the exact missing condition, proving the drift notification was genuinely unimplemented (not coincidentally passing). Green#1 (Turn 93): the helper plus its healthy-path call landed; the run returned `1 passed`. Gating half — Red#2 (Turn 95): `tests/suites/unit/adapters/inbound/test_session_notification_toggles.py` was authored — two unit-layer gate tests that drive the REAL helpers directly. The drift-gate test failed `AssertionError` (the advice was still emitted despite the disabled `checks.prompts_templates` toggle); the update-gate test failed `TypeError: _display_update_notification() takes 1 positional argument but 2 were given` (the helper lacked the config seam) — both exact missing conditions. Green#2 (Turn 97): both gates plus the threaded `container` at both call sites landed; the combined run returned `3 passed` (2 unit + 1 acceptance).

**Refactor (Phase 2 Step 3).** No file-scoped refactor warranted: the two toggle reads share only the `container.resolve(IConfigService)` line with different keys, so the rule of three is not met and a shared `_is_check_enabled` helper would add indirection without removing genuine duplication. No `[DEBT]` was newly logged.

**Phase 3 Local Recovery.** The Global Run (Turn 98) surfaced `1 failed, 1700 passed, 5 skipped` in `test_session_cli_handlers.py::test_resume_handler_calls_set_session_agent_when_agent_provided`, whose bare `Mock()` container returns a single `Mock(spec=ISessionManager)` for EVERY port. The newly-threaded `_display_update_notification` resolves `IConfigService` and calls `get_setting` → `AttributeError: Mock object has no attribute 'get_setting'`. Classified a LOCAL FLAW (the fix required editing ONLY that existing test file; no out-of-scope production change). The repair stubbed `_display_update_notification` alongside the test's six existing seams, preserving its focus on `set_session_agent` wiring; the two sibling background-check tests use bare truthy mocks and were unharmed. The re-run (Turn 100) was GREEN at `1701 passed, 5 skipped`.

### Harness — Drift/toggle regression + acceptance tests (complete)

**Scope.** The Plan Audit (Turns 105-106) fixed this deliverable to exactly the three genuinely-uncovered cases left after the existing suites, so the additions lock in production behaviour that previously had no direct test:

- **(a) UNIT — absent `.teddy/prompts/` directory.** `tests/suites/unit/core/services/test_init_service_drift.py` gained `test_check_drift_reports_every_prompt_missing_when_prompts_dir_absent`, which imports the `_PROMPT_FILES` manifest as the single source of truth (no shadow list) and asserts that with `.teddy/prompts/` entirely absent every manifest entry reports MISSING while the independent `docs/templates/` half stays clean. This drives the per-file `path_exists` guard — there is no directory-existence shortcut.
- **(b) UNIT — toggles absent from config default to ENABLED.** `tests/suites/unit/adapters/inbound/test_session_notification_toggles.py` gained two symmetric characterization tests whose fake config returns the caller's default for every key (the exact semantics of a config lacking the `checks` block). Each drives the production `get_setting("<key>", True)` default argument: with it `True` the notification fires, and a mutation to `False` would break both — locking the backwards-compatible default.
- **(c) ACCEPTANCE — missing template advises `teddy init templates`.** `tests/suites/acceptance/test_preflight_drift_notification.py` gained `test_start_advises_init_templates_when_a_template_is_missing`, a happy-path scenario of the drift-notification Feature driven through the outermost `teddy start` boundary. It arranges `docs/templates/` with a single local file so template drift is reported under BOTH a per-file classifier and any directory-guarded variant (robust to the one open design question in the template half), and asserts the yellow `teddy init templates` advice appears.

**No production change — mutation-style characterization Reds.** Every new test asserts ALREADY-CORRECT production behaviour, so the Red steps were characterization/regression Reds: each case was reasoned to genuinely drive its target branch (mutation-style), and NO production code was modified to manufacture a failing assertion. This is the intended shape for a Harness deliverable whose purpose is to lock in behaviour already shipped by the Seam and Wiring items.

**Verification.** Focused runs: case (a) `2 passed` (Turn 109), case (b) `4 passed` (Turn 110), case (c) `2 passed` (Turn 111) — four new tests total. Phase 3 (Turn 112): full suite GREEN at `1705 passed, 5 skipped in 8.37s` — the four new tests added to the `1701`-pass Wiring baseline, confirming no regression.

### Refactor — Single-source the canonical-casing helper (complete)

**Production change.** The last remaining inline casing literal in production is gone. `prompt_manager.py` now imports `canonical_agent_name` from `teddy_executor.core.utils.string` (co-located beneath the existing `utils.serialization` import), and the lazy-compose header in `fetch_system_prompt` became `assembled = f"Agent Name: {canonical_agent_name(agent_name)}\n\n{content}"`. The Phase 1 Discovery grep (Turn 116) had pinned the blast radius to exactly this ONE call: `canonical_agent_name` was already consumed by `session_cli_handlers.py` (the CLI banner) and `session_service.py` (both meta-write sites), and NO other inline `.capitalize()` survived in `src/` or `tests/`. Single-sourcing now guarantees the banner, the planning header and the composed prompt header can never drift apart.

**Behaviour-preserving / Green-to-Green.** `canonical_agent_name(a)` returns `a.capitalize()` today, so the refactor emits byte-identical output. No seam break: the helper signature is unchanged and the change only ADDS a consumer, so no Contract → Migration → Cleanup partitioning was warranted.

**One Red-Green cycle (characterization safety net).** Red (Turn 118): `tests/suites/unit/core/services/test_prompt_manager.py` gained a parametrized safety-net test driving upper- and mixed-case agent input through the real header branch; the focused module ran `14 passed` (characterization Green — production already canonicalised, so NO production was changed to manufacture a failure). Green (Turn 119): the import plus the inline-call replacement landed; the focused module stayed `14 passed` with ZERO assertion edits, proving the refactor is behaviour-preserving.

**Phase 3 Integration.** The full suite (`make test`, no filters) ran GREEN at `1707 passed, 5 skipped in 9.21s` — the two new parametrized cases added to the `1705`-pass Harness baseline, confirming no regression. No Phase 3 recovery was required.

### Cleanup — 03-03 contract reversal + spikes/debug no-op (complete)

**Documentation change (the deliverable IS the doc update).** The `03-03-templates-and-init` slice doc gained a **Contract Reversal** section, inserted immediately before its `## Business Goal` header, recording that slice `00-32` Item 1 reversed the auto-init contract so that `docs/templates/` is scaffolded ONLY by the explicit `teddy init templates` subcommand. It enumerates every now-superseded statement in that document (the bare-init Gherkin scenario, the Wiring deliverable row that claimed a folded `Templates:` summary segment, the "Auto-init on startup" note, and Verification step 4) and cites the reversal's acceptance contract in `tests/suites/acceptance/test_templates_auto_init.py`.

**Spikes removal is a confirmed NO-OP.** The second half of the deliverable ("remove `spikes/debug/` if present") was verified in Turn 125: no `spikes/debug/` directory exists. The retained `spikes/prototypes/mrp-base-prompt` prototype (owned by slice `03-02`) is out of scope and left untouched.

**Verification.** Phase 3 (Turn 126): full suite GREEN at `1707 passed, 5 skipped` — identical to the Refactor baseline, as predicted for a documentation-only change (no source or test file touched). No Phase 3 recovery was required. This is the slice's LAST deliverable; the 8-item `## Verification` checklist and the Consistency Check run in Phase 5.

## Verification

1. `teddy init` and `teddy start` do NOT create `docs/templates/`; `teddy init templates` does.
2. `teddy start -a pathfinder` writes a composed `pathfinder.xml` to the session folder; a subsequent turn reuses it verbatim.
3. `teddy resume -a developer` recomposes the prompt and removes the stale prompt file.
4. Editing `.teddy/prompts/developer.xml` then `teddy start` emits the yellow `teddy init prompts` message.
5. Deleting a file in `docs/templates/` then `teddy start` emits the yellow `teddy init templates` message.
6. Setting each toggle to false suppresses the corresponding message; a missing toggle defaults to enabled.
7. `teddy start -a PATHFINDER` shows `Agent: Pathfinder` and `Waiting for Pathfinder to respond...`; `meta.yaml` stores canonical casing.
8. Full suite green (`make test`).
