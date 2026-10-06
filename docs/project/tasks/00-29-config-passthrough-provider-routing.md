# Task: Make `llm` Config Pure Pass-Through (Remove the `provider` Special-Case)

## Business Goal
Make the `llm` config section — and the `--provider` CLI flag — behave as pure pass-through to LiteLLM, removing the TeDDy-only `provider` special-case so the code matches its documented behavior and the overloaded "provider" terminology collision disappears.

## Context

**Problem.** Despite the documentation, `LiteLLMAdapter._prepare_completion_params()` still special-cases a TOP-LEVEL `provider` key under `llm:` — for `openrouter/` models only, it moves the value into `extra_body.providers.order` and deletes the key (`litellm_adapter.py`, the `# OpenRouter Provider Routing` block). This directly contradicts two authoritative sources that declare the special-casing REMOVED:
- [docs/project/PROJECT.md](/docs/project/PROJECT.md) — Milestone 2: "Remove `llm.provider` special-casing in `litellm_adapter`; … document pass-through behavior of `llm` config section."
- [docs/architecture/adapters/outbound/litellm_adapter.md](/docs/architecture/adapters/outbound/litellm_adapter.md) — §4: "The adapter does NOT special-case the `llm.provider` config value — the entire `llm` config section passes through transparently to litellm via `params.update(llm_config)`."

**Why it matters (terminology collision).** "provider" is overloaded across three layers:
1. **LiteLLM's "provider" = the gateway**, selected by the model *prefix* (`openrouter/…`, `openai/…`, `anthropic/…`). You cannot switch gateways with a `provider=` argument.
2. **OpenRouter's "provider" = the upstream host** serving a model (`baseten`, `together`, `deepinfra`, …), set via a `provider` object in the request body.
3. **TeDDy's `llm.provider` key** = a custom knob that fed #2 — but it is openrouter-only, accepts a single lowercased value, and only ever sets `order` (no `only`/`ignore`/`sort`/`data_collection`/`zdr`).

**The pass-through alternative (already works today).** Because `params.update(llm_config)` forwards every `llm` key to `litellm.completion()`, users can already configure OpenRouter upstream routing with the documented body shape via `extra_body`:

```yaml
llm:
  extra_body: {provider: {order: ["baseten"]}}
```

Through LiteLLM this becomes the OpenRouter request body — the accepted mechanism (LiteLLM issue [#6857](https://github.com/BerriAI/litellm/issues/6857)). It is STRICTLY more capable than the `provider` special-case (full `order`/`only`/`ignore`/`sort`/`data_collection`/`zdr` support; [OpenRouter provider-selection](https://openrouter.ai/docs/guides/routing/provider-selection)).

**Hard constraint — the removal is ATOMIC.** A top-level `provider=` kwarg to `litellm.completion()` RAISES (`unexpected keyword argument 'provider'` — litellm #6857; the OpenRouter exception surfaces as `Completions.create() got an unexpected keyword argument 'provider'`). Therefore the adapter's special-case block AND the `--provider` CLI flag (which produces that top-level key) MUST be removed together; removing only one leaves `--provider` erroring.

**Enumerate every site first:**

```shell
git grep -n "provider" -- src/teddy_executor
```

## Implementation Steps

### Step 1: Remove the special-case in the adapter
- **File:** [src/teddy_executor/adapters/outbound/litellm_adapter.py](/src/teddy_executor/adapters/outbound/litellm_adapter.py)
- **Change:** In `_prepare_completion_params`, delete the ENTIRE `# OpenRouter Provider Routing` block (the `target_model`/`provider = params.get("provider")` lookup, the `params["extra_body"]["providers"] = …` assignment, and `del params["provider"]`). After removal, `params` must be exactly what `params.update(llm_config)` produced (plus the timeout/model defaults). The `llm` section is then pure pass-through.

### Step 2: Retire the `--provider` CLI flag
- **File:** [src/teddy_executor/__main__.py](/src/teddy_executor/__main__.py)
- **Change:** Remove the `provider: Optional[str] = typer.Option(None, "--provider", …)` parameter and the `provider=provider` argument from BOTH the `start` command (~lines 194-195 / 237) and the `resume` command (~lines 446-447 / 486). Retiring the flag is the clean consequence of "pass through": `--model` already switches models (and therefore gateways), and OpenRouter upstream routing moves to the `extra_body` config key.
- **Alternative (only if the CLI capability must be preserved):** repoint `--provider` so it merges `{"provider": {"order": [value]}}` into the request's `extra_body` at the CLI boundary instead of relying on the removed special-case. Confirm the preferred option with the project owner BEFORE implementing.

### Step 3: Remove the `provider` override threading (handlers → planning)
- **File:** [src/teddy_executor/adapters/inbound/session_cli_handlers.py](/src/teddy_executor/adapters/inbound/session_cli_handlers.py)
- **Change:** Remove the `provider` parameter from the handler signatures (`handle_new_session`, `handle_resume_session`, `handle_plan_generation`) and their `provider=provider` forwards. Remove the `if provider: meta["provider"] = provider` block ONLY after verifying it exclusively carried the CLI override (see Step 5).
- **File:** [src/teddy_executor/core/services/planning_service.py](/src/teddy_executor/core/services/planning_service.py)
- **Change:** Remove the `provider` parameter and the `overrides["provider"] = provider` assignment. Audit the `provider=meta.get("provider")` site (~line 116) to confirm it is part of the removed override path and not the display path.

### Step 4: Remove the `provider` session option
- **File:** [src/teddy_executor/core/services/session_service.py](/src/teddy_executor/core/services/session_service.py)
- **Change:** Remove the `if options.provider: meta_data["provider"] = options.provider` block (~lines 164-165) that records the CLI override into session metadata.

### Step 5: Do NOT touch the DISPLAY provider path (verify, then leave intact)
- The ACTUAL serving provider is extracted from `response._hidden_params["provider"]` (e.g. by `PromptManager.update_meta`) for CLI/TUI telemetry and persisted under the SAME `provider` meta key (`session_service.py` persist-key list; `core/domain/models/session.py` meta field). This is an INDEPENDENT, intended mechanism. Keep it working — only the CLI-override → request-routing path is being removed. This is the single highest-risk part of the task; audit carefully.

### Step 6: Tests
- Add a regression test proving `llm.extra_body` passes through unchanged to `litellm.completion()` (drive `_prepare_completion_params` and assert `params["extra_body"] == {"provider": {"order": ["baseten"]}}` with NO top-level `provider` key produced).
- Add a test asserting a top-level `provider` key under `llm` is NO LONGER transformed (the special-case is gone).
- Update/remove any test that exercised the `--provider` threading (e.g. `tests/suites/unit/adapters/inbound/test_bug_16_model_override_message.py`, `test_bug_24_model_override_on_resume.py`, `test_session_cli_handlers*.py` — verify via `git grep -n provider -- tests`).

### Step 7: Docs
- **File:** [docs/architecture/adapters/outbound/litellm_adapter.md](/docs/architecture/adapters/outbound/litellm_adapter.md)
- **Change:** §4 already states the pass-through; remove the now-stale `extra_body.providers.order` reference and reword the `:nitro`/`:floor` note to attribute those suffixes to OpenRouter (routing variants), not a TeDDy convention.

## Verification
1. `_prepare_completion_params` returns the `llm` config unchanged (no `provider` special-casing); a unit test asserts `extra_body` passes through verbatim.
2. `teddy start --help` / `teddy resume --help` no longer list `--provider`; no top-level `provider` kwarg can reach `litellm.completion()`.
3. Setting `llm.extra_body: {provider: {order: ["baseten"]}}` in `.teddy/config.yaml` produces a request routed via `extra_body` (mocked `litellm.completion` call asserts the kwarg).
4. The DISPLAY provider still appears in telemetry/meta (regression test unchanged and green).
5. `uv run pytest tests/suites/unit/adapters/outbound/test_litellm_adapter*.py -q` passes.
6. Code and docs are consistent with PROJECT.md Milestone 2's "Remove `llm.provider` special-casing" requirement.
7. Full suite green: `uv run pytest` (the post-commit hook enforces this; never bypass).
