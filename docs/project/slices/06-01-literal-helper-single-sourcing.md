# Slice: Single-Source Production Literals and Helpers
- **Status:** Planned
- **Milestone:** [Milestone 6: Cross-Cutting Consolidation](/docs/project/milestones/06-cross-cutting-consolidation.md)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [ISessionManager](/docs/architecture/core/ports/outbound/session_manager.md), [SessionService](/docs/architecture/core/services/session_service.md), [InitService](/docs/architecture/core/services/init_service.md), [LiteLLMAdapter](/docs/architecture/adapters/outbound/litellm_adapter.md), [ConsoleTooling](/docs/architecture/adapters/outbound/console_tooling.md)
- **Scope Slug:** `literal-helper-single-sourcing`

## Goal
Give every value that two or more modules must agree on one authoritative definition, so a change lands in one place instead of four, and delete the duplicated helper bodies that must be kept in manual lockstep.

## Context
- The session artifact filenames are the measured worst case, not the milestone's named literals. In `src`, `plan.md` is spelled in 12 modules, `meta.yaml` in 10, `report.md`, `turn.context`, and `session.context` in 8 each, the sessions root in 4, and `.web_cache.json` in 1. These names are the on-disk protocol the harness asserts against, so one drifted spelling creates a second layout that only one code path reads.
- The literals the milestone names explicitly: the `cl100k_base` encoding name (`litellm_adapter.py` + `cli_helpers.prewarm_imports`); `TEDDY_LLM_API_KEY` (`session_cli_handlers.py` + the bundled `config.yaml`, which is data rather than code, so the definition must be reachable from both); the `"disabled"` editor sentinel (`console_tooling.py` + `session_cli_handlers.py` + `test_environment.py`); the "Editor is disabled in config" message (`console_interactor_ask_loop.py` + `console_interactor.py`); the `## User Request` heading (`execution_report.md.j2` + `SessionLifecycleManager._append_user_request` + the `^## User Request` preservation regex in `session_service.py`, a third site that silently stops matching when the heading changes); and the `awaiting_reply` key (`session_orchestrator.py` + `session_lifecycle_manager.py`).
- The helpers: the "does this model require an API key?" check (`LiteLLMAdapter.validate_config` + `_llm_model_requires_api_key`); the MESSAGE-action detection iteration (`session_orchestrator.py`); the preservation-arm decision (`SessionService.transition_to_next_turn` + `preserve_turn_in_session_context`); the two function-local `session_orchestrator` imports in `session_lifecycle_manager.py`; the TUI diff-routing predicate, where `_DIFF_FLAGS` decides routing while `get_diff_viewer_command()` honours the `diff_flags` override, so a user-supplied override is silently ignored for an unknown editor; and `InitService`'s asymmetric manifest, where `_TEMPLATE_FILES` and `_PROMPT_FILES` are module constants but the config manifest is an inline literal inside `_init_config_dir`.
- Ten function-local `os` imports across eight files — `cli_helpers.py:64`, `textual_plan_reviewer_execution.py:19`, `console_interactor.py:66,112`, `litellm_adapter.py:100`, `context_service.py:367`, `execution_orchestrator.py:246,323`, and `session_loop_guard.py:90,100` (`import os as _os`) — are exactly the ten `PLC0415` suppressions in `src`. The lazy-import mandate exists so `litellm` and `trafilatura` load after startup; `os` costs microseconds, so hoisting it removes the suppression honestly rather than converting it into a helper.
- `validation_rules/helpers.py`'s `resolve_similarity_threshold` reads an action parameter named `edit.similarity_threshold` that no caller sets, because the global config lookup already supplies the threshold.
- Placement: artifact names and report section names are domain vocabulary — the Ubiquitous Language already defines Session Root, Turn, Plan, Execution Report, Turn Context, and Session Context — so they live in `core/domain/models/` where every adapter may import them. The harness may keep its own spellings deliberately; an observer that imports the same constant cannot detect a changed contract.
- Not in scope: the money-rendering law recorded in `ARCHITECTURE.md` has exactly one site today, `session_loop_guard.py:104`, and slices [04-05](./04-05-context-metadata.md) and [04-06](./04-06-context-actions.md) own the formatter that law requires.
- Ordering: [05-02](./05-02-suppression-audit.md) audits the same `PLC0415` suppressions this slice orphans, and [06-05](./06-05-domain-exception-hierarchy.md) edits the same `session_service.py` raises, so a concurrent run needs a separate workspace and a rebase before merge.

## Scenarios

> As a maintainer, I want a renamed artifact to move in one edit.

```gherkin
Given the session artifact names defined in one core module
When I change the turn context filename there
Then every producer and consumer writes and reads the new name
And no module still spells the old one
```

> As a maintainer, I want a duplicated helper to collapse.

```gherkin
Given the two API-key requirement checks
When a model that needs no key is validated
Then both entry points answer from the same function
And a test asserts the two former sites resolve to the same object
```

> As a maintainer, I want a function-local stdlib import gone rather than suppressed.

```gherkin
Given a module that imports os inside a function and suppresses PLC0415
When the slice completes
Then the import sits at module scope
And no suppression remains for that line
```

## Edge Cases
- **Data-side literal**: If the env-var name must also appear in the bundled `config.yaml`, then the YAML value is written literally and a test asserts it equals the Python constant, because a template cannot import code and the identity claim is what prevents drift.
- **Derived regex**: If the `## User Request` heading becomes a constant, then the preservation regex is built from it rather than restating it, because a second copy of the heading is the exact defect being removed.
- **Sentinel versus message**: If the `"disabled"` sentinel and the "Editor is disabled in config" message are both single-sourced, then they stay two definitions, because one is a configuration value the user writes and the other is text the user reads.
- **Awaiting-reply key**: If the key is read and written in different layers, then the constant lives with the session metadata model, because a key defined in an orchestrator forces the manager to import upward.
- **Diff-routing predicate**: If an unknown editor has a user-supplied `diff_flags`, then the predicate returns "registered diff viewer" from the override, because the override is the user's declaration that it is one.
- **Unused threshold branch**: If a grep proves no plan producer emits `edit.similarity_threshold`, then the branch is deleted rather than wired, because an unset parameter path is dead code pretending to be configuration.
- **`PLC0415` residue**: If [05-02](./05-02-suppression-audit.md) has not landed when the hoist happens, then this slice deletes the suppressions it orphans in the same commit, because leaving them makes the audit report a finding that no longer exists.
- **Harness spellings**: If tests currently import a production constant to build a path, then those imports are removed in favour of literal spellings, because a test that shares the constant cannot fail when the constant changes.
- **Manifest symmetry**: If `_CONFIG_FILES` is extracted, then its consumer reads it exactly as `_TEMPLATE_FILES`'s consumer reads that one, because a symmetric manifest is only valuable when the three behave alike.
- **Constant sprawl**: If a value has exactly one reader, then it stays inline, because a constants module that mirrors every literal is indirection rather than single-sourcing.

## Key Unknowns
- [ ] [Harness] Whether the harness currently imports production constants to build expected paths. Design Sensitivity: if it does → those imports are removed first and the expected values become literals, because a shared constant silently redefines correctness; if it does not → the harness is untouched and the slice stays inside `src`.

## Impact
1. `[NEW]` `core/domain/models/session_artifacts.py` — the sessions root and the artifact filenames, plus a helper that composes a turn directory.
2. `[NEW]` The report section-name definition — the `## User Request` heading and its siblings, from which the preservation regex is derived.
3. `[MIGRATE]` The modules spelling each artifact filename — 12 for `plan.md`, 10 for `meta.yaml`, 8 each for `report.md` and the two context files, 4 for the sessions root, 1 for the web cache.
4. `[MIGRATE]` The six named literals — encoding name, env-var name, editor sentinel, disabled message, user-request heading, awaiting-reply key — one definition each with its consumers importing it.
5. `[MIGRATE]` The four duplicated helpers — API-key check, MESSAGE detection, preservation-arm decision, diff-routing predicate — plus `InitService`'s `_CONFIG_FILES`.
6. `[PRUNE]` The ten function-local `os` imports with their `PLC0415` suppressions, the two function-local `session_orchestrator` imports, and the unused `edit.similarity_threshold` branch.
7. `[MIGRATE]` The five component pages above — record the single definition each component now consumes.

## Deliverables
- [ ] **Interface** — Land the two new core modules (artifacts and report sections) and the four helper signatures, documented on the pages that own them.
- [ ] **Harness** — Add the identity tests: for each former duplication, import the canonical definition from both former consumer sites and assert it is the same object; assert the bundled YAML env-var value matches the Python constant.
- [ ] **Migration** — Point every consumer at the canonical definition, hoist the function-local `os` imports, and delete the unused threshold branch.
- [ ] **Cleanup** — Remove the `PLC0415` suppressions this slice orphans, and confirm the suite is green with no behaviour change.

## Implementation Notes

## Verification
1. **Literals single-sourced:**
   Run `git grep -c "plan.md" -- src` and `git grep -c "meta.yaml" -- src`.
   Verify each returns only the canonical definition module.
2. **Identity proven:**
   Run the new harness tests.
   Verify each asserts object identity between the canonical definition and both former sites.
3. **No laziness regression:**
   Time `uv run teddy --help`.
   Verify startup stays under the recorded baseline, because the hoist must not pull a heavy module into import time.
