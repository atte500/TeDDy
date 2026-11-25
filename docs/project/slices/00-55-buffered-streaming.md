# Slice: Buffered Streaming Transport
- **Status:** Planned
- **Milestone:** None (ad-hoc slice)
- **Depends On:** None
- **Specs:** None
- **Prototype:** [Stream reconstruction probe](/spikes/prototypes/llm-stream-buffering/probe_stream_rebuild.py), [Reader acceptance probe](/spikes/prototypes/llm-stream-buffering/probe_rebuilt_readers.py)
- **Component Docs:** [LiteLLMAdapter](/docs/architecture/adapters/outbound/litellm_adapter.md), [ILlmClient](/docs/architecture/core/ports/outbound/llm_client.md)
- **Scope Slug:** `buffered-streaming`

## Goal
A generation that outlives a proxy's idle timer is killed mid-flight even though the model is still working. Let `llm.stream: true` mean "carry this request as a stream", drain that stream in the adapter, and hand the rest of the system one complete response, so the connection stays fed while plan extraction, costing, and telemetry keep processing exactly as today.

## Context
- `LiteLLMAdapter._prepare_completion_params`: Forwards every `llm.*` key verbatim to `litellm.completion`, so a truthy `stream` reaches the library. Both that method and `validate_config` currently reject it.
- `litellm` 1.83.7 (pinned `>=1.83.7,<1.83.8`): `completion(stream=True)` returns a `CustomStreamWrapper` with no `choices` attribute at all — reading it raises `AttributeError`, not an empty list. `PlanningService._extract_plan_content` guards on `hasattr(response, "choices")`, returns `""`, and `_perform_generation_with_retry` spends every attempt on an empty plan before writing an empty `plan.md`. The guard is load-bearing, which is why it cannot be removed before the drain exists.
- `litellm.stream_chunk_builder`: Rebuilds the drained chunks into a `ModelResponse` carrying `content`, `finish_reason="stop"`, `model`, and a working `completion_cost`. Measured on the pinned version with `mock_response`.
- `litellm.stream_chunk_builder` usage handling: Calls `processor.calculate_usage`, so counts are computed from the chunks rather than relayed from a usage chunk. Measured with and without `stream_options={"include_usage": True}`, both yielding `prompt_tokens=9`. litellm injects `include_usage` only in its proxy request path, never for direct SDK calls.
- Measured reader acceptance: the rebuilt response passed through the unmodified adapter as `TokenUsage(prompt_tokens=9, cached_tokens=0)`, a recomputed cost of `4.25e-05`, and `_teddy_cost_recorded=True`. No existing reader changes.
- Measured cost gap: `_hidden_params["response_cost"]` is `None` on the rebuilt response, so the reported figure is lost and the registry recompute supplies the cost. `litellm.include_cost_in_streaming_usage` is the candidate to restore it.
- `PlanningService` and `run_interruptible`: The planning phase runs on a daemon worker and is interrupted by a future poll, so a buffered drain changes nothing about quit handling. Streaming is a transport detail inside one adapter call, never a chunk feed to the caller.
- External limits (documented defaults, not behaviour this suite can pin): Cloudflare's 524 fires after 125 seconds without response bytes and only an Enterprise plan can raise it; nginx's `proxy_read_timeout` defaults to 60 seconds and `proxy_buffering` defaults to `on`. A stream feeds both timers only once tokens flow, so prompt evaluation stays uncovered, and `proxy_buffering on` can still delay client delivery.
- `README.md`: States that all `llm.*` settings pass through to LiteLLM. That sentence becomes accurate again once the key is honoured, so no README change is needed.
- Guard wording is subsumed: this slice deletes the rejection message outright, so a message-only refinement does not need a separate change.
- Transport decision (settled): Streaming is opt-in through `llm.stream`, or a persona-level `agents.<persona>.stream`, never the default transport. The rebuild is still unproven behind OpenRouter for non-OpenAI upstreams, so making it every request's transport would put the least-tested path on every user's happy path.

## Scenarios

> As a user whose generation outlives my proxy's read timeout, I want the request to travel as a stream so that my own ingress stops deciding whether the turn succeeds.

```gherkin
Given a proxy whose read timeout is shorter than the generation
And llm.stream is set to a truthy value
When a turn issues its completion
Then the request travels as a stream that keeps the connection fed
And the rebuilt response yields the same plan content, cost, and token usage as a non-streamed turn
```

> As a user who never set the key, I want the transport untouched.

```gherkin
Given llm.stream is absent or falsy
When a turn issues its completion
Then the request is issued non-streamed and its response is used directly
And no chunk is drained or rebuilt
```

> As a user whose stream breaks mid-flight, I want a loud failure instead of a partial plan.

```gherkin
Given a streamed completion fails after some chunks have arrived
When the turn processes the failure
Then the failure surfaces as an LLM error inside the existing retry loop
And no partial content is written as a plan
```

## Edge Cases
- **String `"true"`**: If `${VAR}` interpolation yields the literal string, then the switch still reads as enabled, because a bare `bool("false")` would also read as enabled and silently stream.
- **Persona-level switch**: If `agents.<persona>.stream` is truthy, then that persona streams and every other persona keeps the non-streamed path, because the overlay merges into the same parameter map.
- **Falsy or absent**: If the value is `false`, `"false"`, or absent, then the non-streamed path is byte-identical to today, because the drain branch is never entered.
- **Empty rebuilt content**: If the rebuilt response carries blank content, then it falls through to the existing empty-content retry loop, because a blank plan is the defect this slice's predecessor existed to prevent.
- **Builder yields nothing**: If the builder returns `None` because no chunks accumulated, then the adapter raises `LlmApiError`, because returning `None` would fail later with an unrelated `AttributeError` and hide the cause.
- **No injected `stream_options`**: If the request is streamed, then the adapter adds no `stream_options`, because usage is computed from the chunks and a provider may reject an unknown parameter.
- **Hydration retry**: If a completion fails with a not-found error and the adapter retries after hydrating model metadata, then that retry rebuilds too, because it forwards the same merged parameters.
- **Cost provenance**: If the turn streams, then the cost comes from the registry recompute and the recorded-cost flag still drives the Session Cost line, because the rebuilt response reports no cost of its own.

## Key Unknowns

- [x] [Domain] Opt-in via `llm.stream`: Settled by product decision — streaming is enabled per project through `llm.stream`, or per persona through `agents.<persona>.stream`, and never automatically. Design Sensitivity: the truthy-flag check becomes the transport switch and the non-streamed path stays byte-identical, so no provider path, telemetry reader, or default call shape has to assume streaming.
- [ ] [Technical] Rebuild fidelity behind OpenRouter for non-OpenAI upstreams: Whether `stream_chunk_builder` reconstructs content, `finish_reason`, and usage when the upstream is Anthropic or a local model reached through OpenRouter, where usage may arrive only on a final chunk or not at all. Design Sensitivity: if usage is absent → prompt tokens read `0` and the cache ratio silently degrades, so the slice must either document the degradation or send `include_usage`; if present → every reader stays untouched.
- [ ] [Technical] Reported-cost survival across the rebuild: The probe measured `_hidden_params["response_cost"]` as `None` on a rebuilt response. Whether `litellm.include_cost_in_streaming_usage` restores the reported figure. Design Sensitivity: if it cannot → a BYOK request records list price instead of the upstream spend, a telemetry regression the slice must accept or flag; if it can → the fix is one library flag at the call site.
- [ ] [Harness] Driving the drain deterministically without patching the global module: The adapter reaches litellm only through `_litellm_provider`, and module patching is forbidden. Whether a scripted chunk sequence plus a `stream_chunk_builder` answer on `FakeLitellmProvider` is enough, or the rebuild needs its own injected seam. Design Sensitivity: if the provider double suffices → no new constructor parameter and the Milestone 5 patch migration stays clean; if not → the adapter gains a builder seam and its composition-root registration changes.

## Impact
1. `[EXTEND]` `LiteLLMAdapter.get_completion` — When the merged parameters carry a truthy `stream`, drain the wrapper and return one rebuilt complete response, so the port's "one complete response" postcondition holds for both transports.
2. `[EXTEND]` `LiteLLMAdapter` — Route both `litellm.completion` call sites (`get_completion` and `_handle_hydration_retry`) through one request-and-collect helper, so the hydration retry cannot hand a wrapper to a caller.
3. `[EXTEND]` `FakeLitellmProvider` — Answer a scripted chunk sequence and `stream_chunk_builder`, so the drain path is driveable through the existing injection seam with no module patching.
4. `[MIGRATE]` `docs/architecture/adapters/outbound/litellm_adapter.md` — Replace the `stream_rejected` class invariant and the `Proxy timeouts and the rejected llm.stream` section with the supported transport option, its two limits, and the cost-provenance caveat.
5. `[MIGRATE]` `docs/architecture/core/ports/outbound/llm_client.md` — Replace the truthy-`stream` precondition and its `ConfigurationError` clause with the transport option, keeping "one complete response" as the postcondition.
6. `[PRUNE]` `_STREAM_REJECTION_MESSAGE`, the preflight append in `validate_config`, the merge-point guard in `_prepare_completion_params`, and the guard tests — Remove in the same commit that lands the drain, because removing the guard alone reintroduces the silent empty plan. `_is_truthy_flag` survives as the switch normalizer.

## Deliverables
- [ ] **Interface** — State the new `get_completion` postcondition (a truthy merged `stream` returns one rebuilt complete response, never a wrapper) and expose the chunk builder through the injected provider seam.
- [ ] **Harness** — Extend `FakeLitellmProvider` with a scripted chunk sequence and a `stream_chunk_builder` answer, so the drain path is driven through the existing seam without importing or patching litellm.
- [ ] **Wiring** — Honour a truthy merged `stream` by draining and rebuilding before returning, route both `litellm.completion` call sites through one helper, and remove the preflight append and the merge-point guard in the same commit.
- [ ] **Adapter** — Prove the real library boundary: draining a real `CustomStreamWrapper`, the rebuild's content and finish reason, usage without `include_usage`, cost from the recompute, and the recorded-cost flag.
- [ ] **Migration** — Rewrite the rejection in `litellm_adapter.md` and `llm_client.md` as the supported transport option with its two limits and the cost-provenance caveat.
- [ ] **Cleanup** — Delete `_STREAM_REJECTION_MESSAGE` and the guard tests, confirm no code path hands a stream wrapper to a caller, and confirm the README's pass-through sentence is accurate again.

## Implementation Notes
Pending implementation. The prototype probes under `spikes/prototypes/llm-stream-buffering/` record the baseline this slice builds on; delete them once the Adapter deliverable's coverage subsumes them.

## Verification
1. **Streamed turn completes:**
   Set `llm.stream: true` in `.teddy/config.yaml` and run `uv run teddy start -m "hello"`.
   Confirm the turn writes a `plan.md` and the Session Cost line shows a dollar figure.
2. **Default path untouched:**
   Remove the key and run the same command.
   Confirm the turn proceeds exactly as before and no behaviour changed.
3. **Proxy survival and its limit:**
   Behind an nginx with `proxy_read_timeout 60`, run a generation longer than 60 seconds with `llm.stream: true`.
   Confirm the turn survives, then confirm from the component doc that prompt evaluation alone is still uncovered by the stream and that `proxy_buffering off` is required for delivery.
