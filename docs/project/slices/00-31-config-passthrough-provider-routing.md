# Slice: Config Passthrough Provider Routing

- **Status:** In Progress
- **Milestone:** [Milestone 2: Stability & Infrastructure](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [Task Brief: Config Passthrough Provider Routing](/docs/project/tasks/00-29-config-passthrough-provider-routing.md)
- **Prototype:** N/A
- **Component Docs:** [LiteLLMAdapter](/docs/architecture/adapters/outbound/litellm_adapter.md)
- **Scope Slug:** `config-passthrough`

## Business Goal

Make the `llm` config section – and the `--provider` CLI flag – behave as pure pass-through to LiteLLM, removing the TeDDy-only `provider` special-case so the code matches its documented behavior and the overloaded "provider" terminology collision disappears.

## Scenarios

> As a user, I want to configure OpenRouter provider routing via `extra_body` in `.teddy/config.yaml` instead of via a special `llm.provider` key, so that the config is true pass-through and I have full control over upstream provider selection (order, only, ignore, etc.).

```gherkin
Given a .teddy/config.yaml containing:
  llm:
    extra_body:
      provider:
        order: ["baseten"]
When I run `teddy start`
Then the request to litellm must contain `extra_body` with the exact value
And no top-level `provider` key is produced in the params
```

> As a developer, I want the `--provider` CLI flag removed, so that the overloaded "provider" terminology collision is eliminated and routing is configured only via the pass-through config.

```gherkin
Given the CLI parser
When I check `teddy start --help`
Then the output must not contain "--provider"
When I run `teddy start --provider baseten`
Then the CLI must reject the flag with an error
```

> As a user, I want the session metadata display provider (extracted from `_hidden_params`) to remain unchanged, so that telemetry and TUI display continue to show the actual serving provider.

```gherkin
Given a completed LLM completion with known `_hidden_params["provider"]`
When the response is processed
Then the `provider` key in session meta must still contain the actual serving provider from litellm
```

## Edge Cases

- **Migration fallback**: If a user has been using the old `llm.provider` config key, the removal must not silently ignore it – a validation error should point to the `extra_body` alternative. The `llm` config is pure pass-through, so any key not recognised by litellm will be `unsupported_kwargs` or similar error; we document this migration.
- **No `extra_body` in config**: If `llm.extra_body` is absent, the adapter must not add any provider routing keys. Verified by existing pass-through test.
- **`--model` overrides**: The `--model` flag continues to select the LiteLLM gateway; no `--provider` flag is available to conflict.

## Key Unknowns

- [x] [Technical] Does the `--provider` flag have any callers in tests or documentation? – grep confirmed three test files reference `--provider`; no documentation other than the spec and architecture doc reference it as a current feature (they only document the original special-case removal intent). All test references will be removed as part of the Cleanup deliverable.
- [x] [Technical] Can the display provider path (`_hidden_params`) be verified as independent? – git grep shows `provider` in meta is set exclusively by `PromptManager.update_meta` reading `response._hidden_params["provider"]`; the removed `if options.provider:` block in `session_service.py` is the only other site writing to the same `meta["provider"]` key, so removing it leaves only the display path. Verified safe.

## Implementation Plan

The removal must be atomic: the CLI `--provider` flag and the adapter's `provider` special-case must be removed together because leaving either produces `unexpected keyword argument 'provider'` at runtime. The display provider path must be verified separately and left intact.

Sequence:
1. **Contract (Unit Test)**: Write regression test for `_prepare_completion_params` proving `extra_body` pass-through and no `provider` key production.
2. **Seam (Adapter & CLI)**: Remove the `provider` special-case block in `litellm_adapter.py` and the `--provider` flag from `__main__.py`. Update/remove related tests.
3. **Wiring (Handlers)**: Remove `provider` parameter from `session_cli_handlers.py` handler signatures and forwarding calls.
4. **Logic (Planning Service)**: Remove `provider` parameter from `planning_service.py`.
5. **Migration (Session Options)**: Remove `if options.provider:` block in `session_service.py`.
6. **Cleanup (Docs & Tests)**: Update `litellm_adapter.md` architecture doc, remove stale doc references, remove `--provider` test references, verify display provider path still works.

Test strategy: All new tests are unit tests in existing test files. No new test infrastructure needed.

## Deliverables

- [ ] **Contract** - Write regression test for `_prepare_completion_params` pass-through (extra_body unchanged, no top-level provider).
- [ ] **Seam** - Remove provider special-case in adapter; remove `--provider` CLI flag from start/resume.
- [ ] **Wiring** - Remove provider parameter from session_cli_handlers handler signatures and forwards.
- [ ] **Logic** - Remove provider parameter from planning_service.py.
- [ ] **Migration** - Remove provider option write in session_service.py.
- [ ] **Cleanup** - Update litellm_adapter.md docs; remove `--provider` test references; verify display provider path still works.

## Implementation Notes

(To be filled during implementation)

## Verification

- [ ] `_prepare_completion_params` returns `extra_body` verbatim, no `provider` key produced – unit test passes.
- [ ] `teddy start --help` and `teddy resume --help` do not list `--provider`; passing `--provider` errors.
- [ ] Setting `llm.extra_body: {provider: {order: ["baseten"]}}` in config produces correct Litellm call – mocked assertion passes.
- [ ] Session provider display (from `_hidden_params`) remains in meta – existing display tests pass.
- [ ] Full test suite green: `uv run pytest`.
