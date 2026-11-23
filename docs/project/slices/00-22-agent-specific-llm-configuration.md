# Slice: Agent-Specific LLM Configuration
- **Status:** In Progress
- **Milestone:** None (ad-hoc slice)
- **Depends On:** None
- **Specs:** None (ad-hoc slice)
- **Prototype:** None
- **Component Docs:** None
- **Scope Slug:** `agent-models`

## Goal
Let one project route each agent persona to its own model while `llm.*` stays the shared default, without introducing a second place where a model is decided.

## Context
- `LiteLLMAdapter._prepare_completion_params`: the only merge site. It fetches the whole `llm` block, layers it over the runtime kwargs, drops a blank `api_key`, then applies a per-call `model` last.
- `PlanningService._run_planning_phase`: the only `get_completion` caller in `src/`. It resolves `agent_name` before any model is chosen, then derives `model = meta["model"] or llm.model` and threads it to telemetry, the budget check, the completion, and the cost lookup.
- `YamlConfigAdapter.get_setting`: declared keys go through the typed view; every other key walks the live merged mapping with `${VAR}` interpolation. The `llm.` prefix is exempted from the typed view; `agents.` is not listed as a typed key, so it already resolves through the live walk. `set_setting` rewrites arbitrary dot paths without reformatting.
- `construct_app_config`: fills the typed view and debug-logs unknown top-level groups. `_KNOWN_TOP_LEVEL` holds the schema groups plus `llm`; `agents` is absent, so it currently logs as unknown, and no shape check exists.
- `ILlmClient`: `get_token_count(messages, model=None)`, `get_text_token_count(text, model=None)`, `get_context_window(model=None)`, `supports_pricing(model=None)`, and `get_completion_cost(response, model_override=None)` already accept a model, so no signature needs widening except `get_completion`.
- Model-less call sites that silently answer for the global model: `planning_service.py:141` (`get_token_count`), `session_orchestrator.py:456` and `:466`, and `context_service.py:114` and `:326`.
- `Precedence and metadata semantics (pinned invariant)`: The model resolves highest first from the `--model` flag, then `agents.<persona>.model`, then `llm.model`; `--model` replaces only the `model` key, so persona credentials and global settings still apply. Persisted state contributes only `model_override` (the explicit flag); `model` records the per-turn effective value and `actual_model` the served value, and neither is ever read as a resolution input. A session without `model_override` re-resolves every turn.
- `_sync_and_display_session_meta`: on resume it stamps `llm.model` into `meta["model"]` whenever the values differ. This is the single write that shadows a persona's configuration.
- `PromptManager.update_meta`: overwrites `meta["model"]` only when the key is absent or already equals the served model. `PlanningService` calls `setdefault` first, so a prefixed effective value survives untouched. No change is needed here.
- `SessionService`: writes `meta_data["model"] = options.model` for an explicit override and carries `["model", "actual_model", "provider"]` across turns.
- `_is_llm_api_key_missing` and `_llm_model_requires_api_key`: read only `llm.api_key` and `llm.model`, with no persona concept, so a persona-level key never triggers the interactive setup prompt.

## Scenarios

> As a project maintainer, I want a cheap model for planning and a strong one for architecture, so that a session costs less without losing quality where it matters.

```gherkin
Given .teddy/config.yaml sets llm.model to "openai/gpt-4o" and llm.timeout to 300
And it sets agents.architect.model to "anthropic/claude-sonnet-4-5"
When I start a session with -a architect
Then the completion request uses model "anthropic/claude-sonnet-4-5"
And it still carries the global timeout of 300
```

> As a user working around a provider outage, I want one flag to override every persona, so that I can switch providers mid-project.

```gherkin
Given agents.pathfinder.model is configured
When I start a session with --model ollama/llama3
Then every turn of that session uses model "ollama/llama3"
And the persona's other configured keys still apply
```

> As a user reviewing a plan, I want to switch persona on resume and get that persona's model automatically, so that I do not have to remember a flag.

```gherkin
Given a session was started with no --model
And agents.pathfinder.model and agents.architect.model are both configured
When I run teddy resume -a architect and continue
Then the architect model is used without any further flag
And the previous turn's effective model does not shadow it
```

> As a user who mistyped the config structure, I want a loud failure, so that I do not pay for an unexpected model.

```gherkin
Given .teddy/config.yaml declares agents as a scalar string
When I start a session
Then TeDDy fails with a ConfigurationError naming the agents key
And no completion request is attempted
```

## Edge Cases
- **No `agents` block**: every persona resolves to the global `llm` block, and behaviour is byte-identical to today.
- **Empty persona model**: a blank or whitespace-only `agents.<persona>.model` falls back to `llm.model`; an empty string is never forwarded, because it would reach LiteLLM as an unresolvable model.
- **Case-insensitive match**: `agents.Architect` matches the `architect` persona, consistent with the prompt resolver's casefold stem matching.
- **Case-folded duplicates**: two persona keys differing only in case raise a `ConfigurationError` at load, because case-insensitive matching would otherwise make the winner depend on YAML key order.
- **Unknown persona name**: an entry naming a persona that has no prompt file stays inert and surfaces as a non-blocking preflight warning that names the key, because failing startup on a typo would be worse than a warning.
- **Model override alongside persona credentials**: `--model` replaces only the `model` key, so a persona-level `api_key` or `api_base` still applies.
- **One-level-deep merge**: a persona that declares a mapping-valued key such as `extra_headers` supplies that key's complete value and replaces the global one, matching how runtime parameters already layer over the `llm` block.
- **Legacy turn metadata**: a `meta.yaml` carrying `model` but no `model_override` is treated as display data only, so the session re-resolves from configuration and any override must be re-supplied.
- **Preflight cache**: a successful first turn under one persona must not suppress validation of a different persona's overriding model or key, because the cache is process-wide today.
- **Persona key present, global key missing**: a persona-level `api_key` with an empty `llm.api_key` still triggers the global setup prompt, which is the documented asymmetry; validation then reports against the merged key.
- **Model-less lookup**: any consumer that omits the effective model answers for the global model, so every call site listed under Context must receive it.

## Key Unknowns
None. The pass-through shape mirrors the existing `llm` block, which is already forwarded to `litellm.completion`; the precedence order is pinned under Context; and every model-dependent call site was located through code reading.

## Impact
1. `[NEW]` `resolve_agent_llm_overrides` in `core/domain/models/config_schema.py` — pure overlay extraction with shape validation and case-insensitive persona matching.
2. `[EXTEND]` `ILlmClient.get_completion` — additive optional `llm_overrides` mapping merged over the global block.
3. `[EXTEND]` `LiteLLMAdapter._prepare_completion_params` — layer the overlay between the global block and the per-call model.
4. `[EXTEND]` `construct_app_config` — list `agents` as a known top-level group and validate its shape at load.
5. `[MIGRATE]` `PlanningService` — resolve the overlay and effective model once, read `model_override` only, and thread the model to every consumer.
6. `[MIGRATE]` `ContextService` and `SessionOrchestrator` — pass the effective model to the token-count and context-window lookups that currently omit it.
7. `[MIGRATE]` `session_cli_handlers`, `SessionService`, `PromptManager` — carry `model_override` separately from the per-turn effective `model`.
8. `[PRUNE]` The resume-time write of a configuration-derived model into turn metadata.

## Deliverables

- [x] **Interface** - Add `llm_overrides` to `ILlmClient.get_completion` with a `None` default so existing callers and fakes stay valid. Add `resolve_agent_llm_overrides(agents_block, persona)` to `config_schema.py` returning the persona's partial block or an empty mapping. Add `agents` to `_KNOWN_TOP_LEVEL` and validate its mapping shape from `construct_app_config`, raising `ConfigurationError` for a non-mapping block, a non-mapping persona entry, or case-folded duplicate keys.
- [x] **Harness** - Teach the auto-specced LLM mock registration and any in-memory config double to accept `llm_overrides`, so harness doubles stay bound to the port contract.
- [x] **Wiring** - Connect the CLI entry points end to end: a session start with `-a` picks the persona's model, the startup banner and preflight report that same effective model, and the completion receives both the overlay and the effective model.
- [x] **Core** - Implement the precedence and fallbacks: override first, then the persona entry, then `llm.model`; a blank persona model falls back rather than propagating; persona matching is case-insensitive. Separate the metadata semantics so `model_override` is the only resolution input while `model` records the per-turn effective value. Write and carry `model_override` for an explicit `--model` flag at session creation and resume so the read flip lands without a regression window; the resume-time stamp removal, the model-less call sites, the preflight cache, and the docs stay in Migration.
- [x] **Adapter** - Merge `llm_overrides` into the completion parameters between the global `llm` block and the per-call model, preserving the blank-`api_key` drop and the provider-default behaviour.
- [x] **Migration** - Thread the effective model into the model-less token-count and context-window call sites in `PlanningService`, `ContextService`, and `SessionOrchestrator`. Stop the resume path from writing a configuration-derived model into turn metadata. Make the preflight cache persona-aware. Add a commented `agents:` example to the bundled `config.yaml` and document the precedence, the one-level merge rule, and the global-scope API-key prompt in the README.

## Implementation Notes

### Interface
- `ILlmClient.get_completion` gained `llm_overrides: Optional[Mapping[str, Any]] = None` between `model` and `**kwargs`. `model` stays third, so every existing positional caller is unaffected.
- `resolve_agent_llm_overrides(agents_block, persona)` is total: a non-mapping block or a non-mapping persona entry returns an empty mapping, so runtime extraction never raises. It copies the matching entry into a new dict, because the merged config it reads from is lazily interpolated and must not be mutated. Persona matching uses `casefold()`, mirroring the prompt resolver. A blank `model` is deleted so an empty identifier never reaches the provider.
- `construct_app_config` runs `_validate_agents_block` before the unknown-group logging pass, so load time is the raising seam. A non-mapping `agents` block, a non-mapping persona entry, and two persona keys differing only in case each raise `ConfigurationError` naming the offending key. The duplicate case fails because case-insensitive matching would otherwise let YAML key order decide the winner. A `None` block counts as absent, matching the adapter's merge treating `None` as a deletion.
- `agents` joined `_KNOWN_TOP_LEVEL`, so the group no longer debug-logs as unknown. Nothing else reads that set, and `agents` never enters the typed view, so `construct_app_config` returns `DEFAULT_APP_CONFIG` unchanged when only `agents` is configured.
- The harness needs no edit for the port contract: doubles are registered as `POSIXPathMock(spec=ILlmClient)`, which derives the accepted parameters from the port, so `llm_overrides` is already part of every spec-bound double.
- `LiteLLMAdapter.get_completion` still accepts only `(messages, model, **kwargs)`, so an overlay passed by keyword would land in `**kwargs` and be forwarded to `litellm.completion` as an unknown parameter. No caller passes it yet, and closing that path is the Adapter deliverable.

### Harness
- No double needed editing: the shared LLM double is a `POSIXPathMock(spec=ILlmClient)`, so it accepts and records `llm_overrides` by construction, and `mock_config` stays a `POSIXPathMock(spec=IConfigService)` driven per test.
- No in-memory config fake exists to extend. `tests/harness/setup/bundled_config.py` is only a bundled-YAML loader, so the persona-capable config path is the real `YamlConfigAdapter`. An undeclared `agents.<persona>` block resolves through its live nested walk (`get_setting` falls through after the declared-key and `llm.` checks), and `construct_app_config` shape-validates it at load.
- `tests/suites/unit/test_agent_overlay_harness.py` pins both seams the Wiring and Core cycles lean on: the spec-bound double records an overlay passed by keyword, the real adapter walks a persona block, the persona block coexists with the global `llm` defaults, and a scalar `agents` block raises `ConfigurationError` at load.
- `scripts/demo/fake_llm.py` is an OpenAI-compatible HTTP server, not an `ILlmClient`, so it carries no overlay handling.

### Wiring
- `PlanningService.generate_plan` resolves the persona overlay exactly once via `resolve_agent_llm_overrides(config_service.get_setting("agents", {}), agent_name)`, then derives `model = meta["model"] or llm_overrides.get("model") or llm.model`, so the effective model and the completion overlay cannot disagree.
- The overlay travels `generate_plan` → `_run_planning_phase` → `_perform_generation_with_retry` → `get_completion`. The `llm_overrides` key is added ONLY when the overlay is non-empty, so a project without an `agents` block issues the identical `get_completion(messages=..., model=...)` call shape as before the feature existed; every existing call-args assertion stays byte-identical. The Refactor collapsed the two duplicate invocations into one conditional-keyword call without altering that shape.
- `_echo_config_success` resolves the persona model through the same extractor, guarded by `if agent`, so `start -a` and `resume -a` report the model the planner will use before the first turn.
- `tests/suites/acceptance/test_persona_model_wiring.py` is the end-to-end tracer bullet: with the config double answering `agents.architect` = `{model, timeout}` and a global `llm.model`, a `start -a architect -y` run drives `model="anthropic/claude-sonnet-4-5"` and `llm_overrides={"model": "anthropic/claude-sonnet-4-5", "timeout": 300}` into the completion, and the banner shows the same model.
- Transitional hazards closed by later deliverables: `LiteLLMAdapter.get_completion` still forwards unknown keywords through `**kwargs`, so a real run WITH an `agents` block would pass `llm_overrides` to litellm until the Adapter deliverable merges it (no shipped config declares `agents` yet, and acceptance drives the mocked port). The resume-time `_sync_and_display_session_meta` write of `llm.model` into `meta["model"]` still shadows a switched persona until Migration removes it; the tracer bullet uses a fresh start.

### Core
- `resolve_effective_model(override, persona_model, global_model)` in `config_schema.py` is the one precedence rule: the explicit flag override wins, then the persona entry, then `llm.model`. A blank or non-string candidate is skipped so an empty identifier never reaches the provider; all-blank returns an empty string. Case-insensitive persona matching and the blank-model drop stay in `resolve_agent_llm_overrides`, so the two resolvers do not duplicate that logic.
- `PlanningService.generate_plan` resolves the effective model from `meta["model_override"]` (never `meta["model"]`) through `resolve_effective_model`, then threads the same value to the completion, the cost lookup, the budget check, and telemetry. `model` is display data only: a carried value is no longer a resolution input, so a persona switched on resume re-resolves every turn.
- Metadata separation write side, re-partitioned into Core so the read flip is non-breaking at every commit: `SessionService._initialize_meta_data` writes `model_override` for an explicit `--model` at session creation, `_persist_next_meta` carries `model_override` across turns alongside `model`/`actual_model`/`provider`, and `_sync_and_display_session_meta` records the resume `--model` as `model_override`. The `--model` flag therefore survives the read flip without a regression window.
- Telemetry ordering is `actual_model or meta["model"] or effective_model or llm.model or "unknown"`, so an already-answered or carried display value is preserved while a fresh turn shows the freshly resolved persona model.
- `_echo_config_success` now single-sources `resolve_effective_model` instead of an inline `if model: … else: …` chain, so the banner reports the same precedence the planner uses; the `"unknown"` fallback is passed as the global candidate and accepted as a non-blank string.
- Tests: `test_effective_model_resolution.py` (six resolver cases), `test_planning_model_precedence.py` (override > persona > global, carried `model` not a resolution input, global fallback, fresh-turn telemetry), three `model_override` write/carry cases in `test_session_service_turn_meta.py`, and a resume `model_override` case in `test_session_cli_handlers_resume_meta.py`.
- Integration gate: the full suite is green at 2358 passed, 5 skipped. One `make test` run tripped `test_validator_edit_performance_large_file` (`0.1474s` against a `0.1s` wall-clock budget) under parallel load; three isolated runs pass well under budget and an immediate full re-run is green, so it is a pre-existing timing flake unrelated to this deliverable, not a regression.
- Transitional hazard narrowed, still open until Migration: the resume-time `_sync_and_display_session_meta` arm that stamps `meta["model"]` from `llm.model` no longer affects resolution (which reads `model_override`), but it still shadows the persona model in the telemetry display line on resume. Migration removes that stamp.

### Adapter
- `LiteLLMAdapter.get_completion` now declares `llm_overrides: Optional[Mapping[str, Any]] = None` between `model` and `**kwargs`, so an overlay can never fall into `**kwargs` and be forwarded to `litellm.completion` as an unknown parameter. `Mapping` joined the typing imports.
- `_prepare_completion_params` takes the same optional overlay and layers it with `params.update(llm_overrides)` after `params.update(llm_config)` and before the per-call model is applied. Precedence, lowest first: runtime kwargs, the global `llm` block, the persona overlay, then the per-call model. The plain `dict.update` makes the merge one level deep, so a mapping-valued overlay key (e.g. `extra_headers`) replaces the global value wholesale, matching how runtime parameters already layer.
- The blank-`api_key` drop and the default-timeout arm run AFTER the overlay merge, so a blank persona `api_key` still replaces the global value and is then dropped, restoring the provider-default behaviour (e.g. a dummy key for a keyless local model).
- An absent overlay (`None`) leaves the merged parameters byte-identical to before, so a project without `agents` issues the same completion call shape and every pre-existing merge/retry/hydration assertion is unchanged.
- Tests: four new cases in `test_litellm_adapter.py`: `test_prepare_completion_params_layers_overlay_between_global_and_model` (overlay timeout beats global, per-call model wins last, no `llm_overrides` key survives), `test_get_completion_expands_overlay_and_never_forwards_it` (the overlay keys reach litellm, the `llm_overrides` key never does), `test_prepare_completion_params_overlay_mapping_replaces_global_wholesale` (one-level mapping replacement), and `test_prepare_completion_params_drops_a_blank_overlay_api_key` (blank overlay key falls through to the provider default).
- Refactor: removed a dead duplicate lazy-validation block in `get_completion` — a second `if not self._validated` guard that could never fire because the first guard either raises or sets `_validated = True` — along with its redundant local `ConfigurationError` alias import. Call counts and control flow are unchanged.
- Integration gate: the full suite is green at 2362 passed, 5 skipped (the prior 2358 plus the four new adapter cases).
- Transitional hazard closed: the Wiring note that `get_completion` still forwarded unknown keywords through `**kwargs` is now closed, so a real run WITH an `agents` block no longer leaks `llm_overrides` to litellm.

### Migration
- The effective model now reaches every model-less call site. `ContextService.get_context` gained an additive optional `model`; its `_count_text_tokens` helper forwards `model` only when truthy, so a no-model caller keeps the exact single-argument `get_text_token_count` call shape. `PlanningService` threads the resolved model into `get_token_count` and `get_context`, and `SessionOrchestrator._gather_fallback_context` resolves the model the planner's way (`model_override`, then persona, then `llm.model`) and threads it into `get_context_window`, `get_text_token_count`, and `get_context`.
- The resume path no longer stamps a configuration-derived model. `_sync_and_display_session_meta` writes only an explicit `--model` (as `model_override`); it records no configuration-derived `meta["model"]`, so a switched persona re-resolves every turn and the telemetry display line is no longer shadowed.
- Preflight cache: `_PREFLIGHT_DONE` was write-only and `reset_preflight` had no caller, so the process-wide cache never short-circuited anything. Removal makes validation run every turn, which is the honest form of "persona-aware" when there is no cache to key: a persona switched mid-session is always re-validated.
- Docs: the bundled `config.yaml` carries a commented `agents:` example (inert under `yaml.safe_load`), and the README Configuration section documents the `--model > agents.<persona>.model > llm.model` precedence, the one-level merge, the flag-replaces-only-model rule, and the global-scope API-key prompt.
- Tests: `test_context_service_model_threading.py` (model reaches the token count), `test_session_orchestrator_fallback_model.py` (persona wins, override wins, carried `model` ignored), and the two Local-Recovery assertion updates in `test_planning_service.py` (expect `model=""`) and `test_session_orchestrator_pipeline_suppression.py` (relax `load_turn_meta` to `assert_any_call`).
- Integration gate: the full suite is green at 2368 passed, 5 skipped after the two Local-Recovery fixes.

## Verification
1. **Persona model selected:**
   Add `agents.architect.model: "anthropic/claude-sonnet-4-5"` to `.teddy/config.yaml`, then run `teddy start -a architect`.
   Verify the startup banner shows the architect model and turn telemetry repeats it.
2. **Global fallback for unlisted keys:**
   Keep `llm.timeout` and `llm.max_retries` in the global block without repeating them under the persona.
   Verify the completion still succeeds and the request honours the global timeout.
3. **Flag outranks configuration:**
   Run `teddy start -a pathfinder --model ollama/llama3`.
   Verify the banner and telemetry show `ollama/llama3` for every turn of that session.
4. **Persona switch on resume:**
   Configure both `agents.pathfinder.model` and `agents.architect.model`, start a session without `--model`, then run `teddy resume -a architect`.
   Verify the next turn uses the architect model and `.teddy/sessions/<name>/<turn>/meta.yaml` records `model` as the architect model with no configuration-derived `model_override`.
5. **Metadata separation:**
   Inspect a turn's `meta.yaml` after an overridden session.
   Verify `model_override` holds the flag value, `model` holds the effective model including its routing prefix, and `actual_model` holds the served model.
6. **Malformed structure rejected:**
   Set `agents: "architect"` in `.teddy/config.yaml`, then run `teddy start`.
   Verify the run fails with a `ConfigurationError` naming `agents` before any completion request.
