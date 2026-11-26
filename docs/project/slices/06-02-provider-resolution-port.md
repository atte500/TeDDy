# Slice: Provider Resolution behind `ILlmClient`
- **Status:** Planned
- **Milestone:** [Milestone 6: Cross-Cutting Consolidation](/docs/project/milestones/06-cross-cutting-consolidation.md)
- **Depends On:** [05-08-litellm-probe-seam](./05-08-litellm-probe-seam.md)
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [ILlmClient](/docs/architecture/core/ports/outbound/llm_client.md), [LiteLLMAdapter](/docs/architecture/adapters/outbound/litellm_adapter.md), [PlanningService](/docs/architecture/core/services/planning_service.md)
- **Scope Slug:** `provider-resolution-port`

## Goal
Resolve which provider a configured model routes to behind one `ILlmClient` operation that returns a domain value object, so no caller reaches into `litellm` to ask, and so the answer a preflight check and a key requirement check receive cannot disagree.

## Context
- The requirement is one sentence in the milestone: move litellm provider resolution behind a single `ILlmClient` method. The reason it matters is that provider identity already drives two decisions — whether an API key is required, and which provider name the CLI reports and validates against — and both currently derive it independently.
- The adapter holds a substitutable seam for exactly this surface: `FakeLitellmProvider` exposes `validate_environment`, `get_llm_provider`, and `completion`, which is how the preflight and provider-resolution suites already drive the answer without importing `litellm` behaviour. That seam is what makes a port method testable with a fake rather than a patch.
- Dependency: [05-08](./05-08-litellm-probe-seam.md) migrates the six modules and twenty-four `monkeypatch.setattr` sites — including `test_litellm_adapter_provider_resolution.py` at six sites — onto that seam. Reshaping the port before those tests reach the seam would mean migrating them twice, so this slice follows it.
- Boundary constraint: `ILlmClient` is an outbound port in core, so its return type must be a domain value object. `litellm.get_llm_provider` answers with a tuple that includes the custom provider, and exposing that tuple would leak a third-party shape across the boundary exactly as `WebScraperAdapter` once leaked `trafilatura`.
- The helper duplication this supersedes is measured: the "does this model require an API key?" check exists twice, in `LiteLLMAdapter.validate_config` and in `_llm_model_requires_api_key`, and both derive from the same provider answer.
- Unrelated monetary fact recorded while measuring: the only money format site in `src` is `session_loop_guard.py:104`, so no formatter conflicts with this slice's touch points.

## Scenarios

> As a maintainer, I want one answer to "which provider is this model routed to".

```gherkin
Given a configured model string
When the preflight check and the key-requirement check both resolve its provider
Then both read the same ILlmClient operation
And neither imports the library to ask
```

> As an operator, I want a local OpenAI-compatible endpoint treated as keyless.

```gherkin
Given a model configured with an api_base pointing at a local server
When its provider is resolved
Then the result names the provider and reports that no API key is required
And the preflight check does not prompt
```

> As a maintainer, I want an unparseable model string to fail as a domain rejection.

```gherkin
Given a model string the library cannot map to a provider
When resolution runs
Then it raises a TeddyError subclass naming the model
And no library exception escapes the port
```

## Edge Cases
- **Tuple arity**: If the library returns provider, model, and custom provider, then the value object keeps the provider name and the key requirement only, because the caller never needs the rest and a wider object invites passing it onward.
- **Custom `api_base`**: If a model resolves to a hosted provider name while `api_base` points at loopback, then the resolution reports keyless, because a reachability fact beats a naming convention.
- **Unknown model string**: If resolution fails, then the failure is a raised domain exception rather than a `None` return, because a caller that receives `None` writes its own fallback and the two call sites diverge again.
- **Preflight timing**: If resolution is called during startup, then the library import stays lazy behind the adapter's private getter, because the CLI init budget is a standing architectural law.
- **Cached resolution**: If resolution runs per turn, then it is cached on the adapter keyed by model string, because repeated library calls at the same input are pure waste and this repository already pays for one resolution per preflight.
- **Fake fidelity**: If the fake returns a tuple because the port returns a value object, then the fake is the thing that changes, because a fake that mirrors the library rather than the port hides the leak it is meant to catch.
- **Key-requirement duplication**: If both checks collapse onto the port operation, then one of them is deleted outright rather than delegating to the other, because a wrapper that forwards is the duplication wearing a new name.
- **Provider name in user output**: If the CLI prints the provider name, then it prints the value object's name, because a second derivation of the same string is how the two disagree the next time the library changes.

## Key Unknowns
- [ ] [Technical] Whether a core service reaches `litellm` directly for provider identity, or whether every caller already goes through the adapter. Design Sensitivity: if a core service imports the library → that import is a boundary violation this slice removes and the port method becomes its replacement, which is strictly simpler than the alternative; if all callers already use the adapter → the slice is a contract tightening plus one deletion, and it can land in a single commit.

## Impact
1. `[NEW]` A provider value object in `core/domain/models/` — the resolved provider name plus whether an API key is required, both constrained values rather than raw strings.
2. `[MIGRATE]` `ILlmClient` and its component page — one `resolve_provider` operation with its preconditions, postconditions, and error modes.
3. `[MIGRATE]` `LiteLLMAdapter` — implement the operation over its private library getter, and cache by model string.
4. `[MIGRATE]` `FakeLitellmProvider` — return the value object, so the fake matches the port rather than the library.
5. `[PRUNE]` One of the two API-key requirement checks — the survivor answers from the port operation.
6. `[MIGRATE]` The consumers of provider identity — preflight, the CLI's provider reporting, and the key-requirement gate.
7. `[MIGRATE]` The three component pages above — record the operation and the value object's invariants.

## Deliverables
- [ ] **Interface** — Define the value object and the port operation, with the failure contract stated on the port page.
- [ ] **Harness** — Teach `FakeLitellmProvider` to answer with the value object, and add the keyless-local-endpoint and unparseable-model cases.
- [ ] **Adapter** — Implement the operation over the lazy library getter with a per-model cache.
- [ ] **Migration** — Repoint every consumer of provider identity and delete the duplicated key-requirement check.
- [ ] **Cleanup** — Record the operation on the port, adapter, and planning-service pages, and confirm no core module imports the library.

## Implementation Notes

## Verification
1. **Single source:**
   Run `git grep -n "get_llm_provider" -- src`.
   Verify the only hits are inside `LiteLLMAdapter`'s private getter path.
2. **Keyless endpoint:**
   Configure a model with a loopback `api_base` and run the preflight path.
   Verify it resolves without prompting for a key.
3. **Domain failure:**
   Resolve a nonsense model string.
   Verify a `TeddyError` subclass names it, with no library exception escaping.
