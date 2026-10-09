# Milestone 6: Cross-Cutting Consolidation

- **Status:** Planned
- **Specs:** TBD

## Goal (The "Why")
Eliminate duplicated literals, helpers, and test doubles that currently live in more than one place and must be kept in manual lockstep. Each duplication is a latent drift bug: when one copy changes, the others silently diverge. This milestone single-sources every such concept so the codebase has one authoritative location per concern, consolidates split test organization, and performs a bounded Failure-Transparency sweep. Every item was previously parked in the retired `## Technical Debt` section of `docs/project/PROJECT.md`; with that holding pen removed, each is now scheduled here as an explicit requirement.

## Proposed Solution (The "What")
Extract shared constants and helpers into their canonical modules; consolidate bespoke in-memory test fakes and harness boilerplate into `tests/harness/setup/`; consolidate the split inbound-port contract-test directory; single-source the TUI diff-routing decision; and sweep broad `except` blocks that swallow errors without logging. The work is strictly behavior-preserving and driven out with tests-first at the harness boundary.

## Guidelines (The "How")
- **Test Harness Strategy:**
    - **Single-source proof:** For each extracted constant/helper, add or update a test that imports the canonical definition from both former consumer sites and asserts identity — so a future re-duplication fails loudly.
    - **Shared-fake adoption:** Migrate the bespoke fakes onto the shared harness fake and delete the local copies; the full suite MUST remain green.
    - **Directory consolidation:** `git mv` the straggler contract test into the canonical directory and fix all import and doc references.
    - **Failure-Transparency sweep:** For each broad `except`, either narrow the caught exception type or add debug-level logging before swallowing; legitimate "safe to ignore" cases MUST keep their explicit comment.
- **Poka-Yoke:** Prefer a shared harness fixture over per-suite duplication so the rule-of-three threshold can never be silently exceeded again.
- **No New Behavior:** Every change MUST preserve existing runtime behavior and pass the full suite; this is a consolidation program, not a feature program.

## Technical Specifications

**Format:** Link to Specification Documents in docs/project/specs/. Key contracts and data models can be summarized inline or referenced.

- **Split inbound-port contract tests:** `test_run_plan_use_case_contract.py` lives in `tests/suites/unit/ports/inbound/` while every other `core.ports.inbound` contract test lives in `tests/suites/unit/core/ports/inbound/`. Consolidate into one canonical location.
- **`InitService` manifest constant:** `_TEMPLATE_FILES` and `_PROMPT_FILES` are module-level constants, but the config manifest is an inline string literal inside `_init_config_dir`. Extract a symmetric `_CONFIG_FILES` module constant single-sourced with its consumer.
- **Duplicated production literals (must stay in lockstep):** the `cl100k_base` encoding name (`litellm_adapter.py` + `cli_helpers.prewarm_imports`); the `TEDDY_LLM_API_KEY` env-var name (`session_cli_handlers.py` + bundled `config.yaml`); the `"disabled"` editor sentinel (`console_tooling.py` + `session_cli_handlers.py` + `test_environment.py`); the "Editor is disabled in config" message (`console_interactor_ask_loop.py` + `console_interactor.py`); the `## User Request` section format (`execution_report.md.j2` + `SessionLifecycleManager._append_user_request`); the `awaiting_reply` flag key (`session_orchestrator.py` + `session_lifecycle_manager.py`).
- **Duplicated production helpers:** the "does this model require an API key?" check (`LiteLLMAdapter.validate_config` + `_llm_model_requires_api_key`); the MESSAGE-action detection iteration (`session_orchestrator.py`); the preservation-arm decision (`SessionService.transition_to_next_turn` + `preserve_turn_in_session_context`); the two function-local `session_orchestrator` imports in `session_lifecycle_manager.py`.
- **Shared test fakes (rule of three met):** three dict-backed `InMemoryFileSystem` fakes (`test_session_repository_meta_contract.py`, `test_session_service_turn_meta.py`, `test_session_lifecycle_resume_message_persistence.py`); four `termios` fakes (`test_tty_guards.py`, `test_terminal_cooked_mode_restore.py`, `test_restore_cooked_mode.py`, `test_terminal_quit_key_listener_reader.py`); ask-loop editor/tooling fakes across three suites. Also extract a `ports_fixture` of pre-configured port mocks to reduce mock-poisoning risk. Consolidate into `tests/harness/setup/`.
- **Duplicated harness temp-root boilerplate:** `tests/harness/setup/model_registry_cache.py` and `hook_shims.py` each duplicate the `tempfile.mkdtemp()` + `rmtree` lifecycle; extract a shared temp-root helper.
- **TUI diff-routing decision:** the routing predicate reads the static `_DIFF_FLAGS` table while `get_diff_viewer_command()` honours the `diff_flags` override, so a user-supplied `diff_flags` is silently ignored for unknown editors. Single-source the "is this a registered diff editor?" decision.
- **MRP resource-root test setup:** the real-`tmp_path` `MRP.xml` resource-root construction in `test_prompt_manager.py` is duplicated in `test_bug_03_prompt_resolution.py`; extract a shared harness helper.
- **Contract-violating session doubles:** `test_session_replan_loop.py`, `test_session_start_resequencing.py`, and `test_resume_message_threading.py` build their own containers and register a bare `Mock(spec=IInitUseCase)` whose `check_drift()` returns a dynamic Mock (no `__len__`). Extract a shared pre-configured session-container / ports fixture so doubles stay contract-faithful.
- **Silent error swallowing (Failure Transparency):** broad `except` blocks without logging across `cli_helpers.py`, `local_file_system_adapter.py`, `shell_adapter.py`, `web_scraper_adapter.py`, `yaml_config_adapter.py`, `action_executor.py`, `context_service.py`, `session_pruning_service.py`, `session_repository.py`, `update_checker.py`, and `io.py`. Narrow the type or add debug-level logging; keep legitimate "safe to ignore" comments.

## Vertical Slices

High-level checklist of implementation steps. Each entry follows the format `{{MM-NN}}: [Description & Requirements]`.
> Slice definitions will be created by the Architect during the Design phase. The following high-level breakdown is anticipated:
>
> 1. `InitService` manifest constant extraction (`_CONFIG_FILES`), single-sourced with its consumer.
> 2. Production literal single-sourcing (encoding name, env-var name, editor sentinel, disabled message, `## User Request` format, `awaiting_reply` key).
> 3. Production helper single-sourcing (API-key check, MESSAGE-action detection, preservation-arm decision, local imports).
> 4. Shared in-memory test-fake extraction into `tests/harness/setup/` (filesystem + termios + ask-loop fakes + `ports_fixture`).
> 5. Shared harness temp-root helper extraction (`model_registry_cache.py` + `hook_shims.py`).
> 6. Inbound-port contract-test directory consolidation (`test_run_plan_use_case_contract.py`).
> 7. Shared MRP resource-root helper + shared session-container/ports fixture.
> 8. TUI diff-routing predicate single-sourcing.
> 9. Failure-Transparency sweep — broad `except` logging/narrowing.
