# Slice: Proxy Timeout Guidance and the llm.stream Guard
- **Status:** In Progress
- **Milestone:** None (ad-hoc slice)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None. One documentation deliverable and one validation rule, with no unresolved behaviour.
- **Component Docs:** [LiteLLMAdapter](/docs/architecture/adapters/outbound/litellm_adapter.md), [ILlmClient](/docs/architecture/core/ports/outbound/llm_client.md)
- **Scope Slug:** `proxy-timeout-guidance`

## Goal
A user running a local model behind Cloudflare or nginx loses a long generation to a hop idle timer and finds no in-product explanation of why or of what to change. Publish the working recipe, and make the one workaround people reach for fail loudly instead of silently burning three retries on an empty plan.

## Context
- `LiteLLMAdapter._prepare_completion_params`: Forwards every `llm.*` key verbatim to `litellm.completion`. The `llm` block carries no per-key schema, so `llm.stream: true` reaches litellm today.
- Consequence: litellm returns a `CustomStreamWrapper`, `PlanningService._extract_plan_content` finds no `choices` and returns an empty string, `_perform_generation_with_retry` burns `llm.max_retries` attempts, and an empty `plan.md` is written. The silence is the defect, not the flag.
- `LiteLLMAdapter.validate_config`: Already returns human-readable error messages and already runs on every turn through `PlanningService._run_preflight_check`, which raises `ConfigurationError` on a non-empty list. It is the existing loud-failure seam, so the guard needs no new plumbing.
- Cloudflare (external): Error 524 fires when a proxied origin sends no response bytes within the Proxy Read Timeout, 125 seconds by default. Only the Enterprise plan can raise it, up to 6,000 seconds.
- Zero-code route: Cloudflare documents a DNS-only (grey cloud) subdomain as the remedy for requests expected to exceed that ceiling, which removes the edge from the request path and leaves nginx as the only timer. It requires a directly reachable origin, so it is unavailable behind CGNAT or behind a Cloudflare Tunnel that stays proxied.
- nginx (external): `proxy_read_timeout` defaults to 60 seconds and measures the gap between successive upstream reads; `proxy_buffering` defaults to `on`, which delays a streamed body.
- TeDDy's own ceiling: `llm.timeout` defaults to 300 seconds, so a 30-minute generation still dies client-side after both proxies are relaxed. The recipe is incomplete without it.
- Honest limit: Nothing client-side prevents the timeout. A heartbeat has no addressee, because both hops measure response-direction silence, and reconnecting restarts prompt evaluation from zero, because chat completions is stateless with no job handle to resume.
- Decision: Streaming is rejected as a half measure. It keeps the connection alive only once generation starts, leaving prompt evaluation and both timeout ceilings untouched, and it depends on the same proxy settings that solve the problem outright.
- Design invariant: The plan is still validated before presentation, and `plan.md` is written only after a completion succeeds.

## Scenarios

> As a user whose long generation dies behind a proxy, I want the documented recipe so that I can fix my own ingress without tracing the adapter.

```gherkin
Given a user running a local model behind Cloudflare and nginx
When a long generation fails with 524 or 504
Then the LiteLLMAdapter component doc names the ceiling, the DNS-only route, the nginx settings, and the llm.timeout caveat
And it states the precondition that rules the DNS-only route out behind CGNAT or a proxied tunnel
```

> As a user who reached for the obvious workaround, I want a clear refusal instead of three silent retries.

```gherkin
Given llm.stream is set to a truthy value
When a turn starts
Then preflight fails with a message naming the key, explaining that streaming is unsupported, and pointing at the proxy recipe
And no completion request is issued and no plan file is written
```

> As a user who never set the key, I want the default path untouched.

```gherkin
Given llm.stream is absent or falsy
When validate_config runs
Then it returns exactly the messages it returns today
```

## Edge Cases
- **Boolean `true`**: If `llm.stream: true`, then validation reports the key, because the pass-through would silently break the turn.
- **String `"true"`**: If env interpolation yields the string `"true"`, then validation reports the key, because a truthy non-empty string enables the same broken path.
- **`false` or absent**: If the key is `false`, `"false"`, or absent, then validation reports nothing, because the default path is unchanged.
- **Message quality**: If the key is reported, then the message names `llm.stream`, states that streaming is unsupported by design, and points at the proxy guidance, because a vague refusal only relocates the confusion.
- **No artifact left behind**: If preflight rejects, then `plan.md` is never written, because a turn that cannot proceed must not leave a file behind.
- **Auth error ordering**: If the key is rejected alongside a missing API key, then both messages appear, because preflight reports the complete set rather than the first fault.

## Key Unknowns
None. The pass-through, the extraction path, and the preflight seam are established by static reading, and both deliverables are one documentation change plus one validation rule.

## Impact
1. `[EXTEND]` `LiteLLMAdapter.validate_config` — Append a message when `llm.stream` is truthy, accepting a YAML boolean or the `"true"`/`"false"` string env interpolation produces.
2. `[MIGRATE]` `docs/architecture/adapters/outbound/litellm_adapter.md` — Record that streaming is rejected and why, and document the proxy recipe in the parameter-merge section.
3. `[PRUNE]` The silent empty-plan path — Once validation rejects the key, it can no longer reach the completion call.

## Deliverables
- [x] **Interface** — Extend `validate_config` with the `llm.stream` rejection and unit tests for boolean `true`, string `"true"`, `false`, `"false"`, and absent.
- [x] **Wiring** — Prove the preflight seam end to end: a `PlanningService`-level test asserting `ConfigurationError` is raised before any completion call and that no plan file is written.
- [ ] **Migration** — Document streaming's rejection and the proxy recipe (the 125 second Cloudflare ceiling, the DNS-only route with its CGNAT and tunnel precondition, `proxy_read_timeout`, `proxy_buffering off`, and `llm.timeout`) in the parameter-merge section of `litellm_adapter.md`.
- [ ] **Cleanup** — Confirm no remaining code path can hand `llm.stream` to the completion call, and that the component doc's parameter-merge section states the rejection.

## Implementation Notes
- The proxy recipe lives only in the `LiteLLMAdapter` component doc. The user-facing README is deliberately left alone: a deployment-specific ingress recipe reads as bloat there and duplicates the adapter contract that already owns the `llm.*` pass-through.

- **Interface:** `validate_config` appends the `llm.stream` rejection before the `if not errors:` gates, so a missing API key and a truthy flag are reported together instead of the first fault masking the second. `_is_truthy_flag` normalizes the value: a string compares case-insensitively against `"true"`, because env interpolation yields the literal `"false"` and a bare `bool()` would read it as enabled; non-strings fall back to native truthiness. Covered by `tests/suites/unit/adapters/outbound/test_litellm_adapter_stream_guard.py`.
- **Interface:** The two retry tests in `test_litellm_retries.py` built their config double with a blanket `get_setting.return_value = {"model": "gpt-4o"}`, so every key resolved to that dict and `llm.stream` came back truthy. They now use the shared `mock_config` fixture, which answers per key and leaves the flag absent.
- **Wiring:** `test_preflight_rejects_truthy_stream_before_completion_or_plan_write` assembles `PlanningPorts` by hand with the real `LiteLLMAdapter` on the `llm` field and harness doubles for the other six ports, rather than overriding the container's `ILlmClient` registration: `punq` shadows a re-registered instance, so an override can silently fail to take effect. The test asserts the boundary three ways — the raise matched on `llm.stream`, `provider.completion_calls == []`, and `mock_fs.write_file` never called. The last one is stronger than the deliverable's wording: `_run_preflight_check()` runs before the `input.md` write, so an uncalled `write_file` proves neither turn artifact was produced, not merely `plan.md`.
- **Wiring:** The litellm provider double moved out of the adapter test module into `tests/harness/setup/litellm_doubles.py` as `FakeLitellmProvider`, now recording every `completion` call and raising `AssertionError` if the request path is reached. Both the adapter unit tests and the service boundary test therefore share one fake, and the swap was verified behaviour-neutral (6 passes before and after).

## Verification
1. **Loud rejection:**
   Set `llm.stream: true` in `.teddy/config.yaml` and run `uv run teddy start -m "hello"`.
   Confirm the turn fails with a message naming `llm.stream`, and that no `plan.md` appears in the turn directory.
2. **Default path untouched:**
   Remove the key and run the same command.
   Confirm the turn proceeds normally.
3. **Documentation completeness:**
   Read the parameter-merge section of `docs/architecture/adapters/outbound/litellm_adapter.md`.
   Confirm it names the 125 second ceiling, the DNS-only route, the CGNAT and tunnel precondition, `proxy_read_timeout`, `proxy_buffering off`, and `llm.timeout`.
