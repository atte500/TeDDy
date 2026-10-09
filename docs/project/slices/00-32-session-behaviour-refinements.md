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
- [ ] **Logic** — Item 6: canonicalise agent casing in `_echo_config_success` and meta persistence.
- [ ] **Contract** — Item 5: add the two config toggle keys to the bundled `config.yaml` (additive; read via `IConfigService.get_setting`).
- [ ] **Seam** — Items 3/4: a drift-check helper comparing user files against bundled defaults.
- [ ] **Wiring** — Items 3/4/5: emit the drift notification at the start/resume preflight and gate it (plus the update notification) by the toggles.
- [ ] **Harness** — Regression/unit tests for the drift checker, composed-prompt persistence+reuse, canonical casing, and the config-toggle defaults; add an acceptance test for the (toggle-gated) drift notification.
- [ ] **Refactor** — Single-source the canonical-casing helper (avoid duplicating the stem→`capitalize()` logic).
- [ ] **Cleanup** — Update the `03-03-templates-and-init` slice doc to record the reversed explicit-only contract; remove `spikes/debug/` if present.

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

## Verification

1. `teddy init` and `teddy start` do NOT create `docs/templates/`; `teddy init templates` does.
2. `teddy start -a pathfinder` writes a composed `pathfinder.xml` to the session folder; a subsequent turn reuses it verbatim.
3. `teddy resume -a developer` recomposes the prompt and removes the stale prompt file.
4. Editing `.teddy/prompts/developer.xml` then `teddy start` emits the yellow `teddy init prompts` message.
5. Deleting a file in `docs/templates/` then `teddy start` emits the yellow `teddy init templates` message.
6. Setting each toggle to false suppresses the corresponding message; a missing toggle defaults to enabled.
7. `teddy start -a PATHFINDER` shows `Agent: Pathfinder` and `Waiting for Pathfinder to respond...`; `meta.yaml` stores canonical casing.
8. Full suite green (`make test`).
