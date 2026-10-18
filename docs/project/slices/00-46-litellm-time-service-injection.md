# Slice: Litellm Retry Time-Service Injection
- **Status:** Planned
- **Milestone:** N/A (ad-hoc slice)
- **Depends On:** N/A
- **Specs:** N/A
- **Prototype:** N/A
- **Component Docs:** [LiteLLMAdapter](/docs/architecture/adapters/outbound/litellm_adapter.md)
- **Scope Slug:** `litellm-time-service`

## Goal
Remove the real 0.5s and 1.0s retry backoff sleeps from the litellm retry path. The `ILlmClient` composition factory and the four named retry tests must receive an injected `ITimeService`.

## Context
- `LiteLLMAdapter` already accepts an optional `time_service` constructor argument. Its `_should_retry_completion` method calls `self._time_service.sleep(delay)` when a time service is present and falls back to the real `time.sleep(delay)` only when it is absent.
- `registries/infrastructure.py` registers the `ILlmClient` factory with `config_service` and `hydrator` only. It omits `time_service`, so a container-resolved adapter sleeps on the real clock.
- `ITimeService` is a runtime-checkable Protocol with `now`, `now_utc`, and `sleep`.
- `register_mock(container, ITimeService)` returns a strict `POSIXPathMock(spec=ITimeService)` that records sleep calls through `side_effect`.
- The retry path computes `delay = 0.5 * (2**attempt)` before the last attempt. A three-attempt failure records `[0.5, 1.0]`.
- The proof spike at [04-time-service-retry-proof.py](/spikes/debug/windows-test-suite-slowness/04-time-service-retry-proof.py) measured 1.50s on the real clock against 0.00s with a recording fake, and captured `[0.5, 1.0]`.
- The integration `test_validation_then_retry_wiring` sleeps 0.5s on one retry. It is outside the four named tests and stays unchanged.

## Scenarios
> As a developer running the test suite, I want container-resolved litellm clients to use the injected time service so retry backoff never sleeps on the real clock.

```gherkin
Given a container that registers ITimeService
When the container resolves ILlmClient
Then the resolved adapter carries the registered ITimeService
```

> As a developer running the litellm retry tests, I want the adapter to use a recording time service so the backoff schedule is asserted without waiting.

```gherkin
Given a litellm retry test that drives three failed completion attempts
When the test injects a recording ITimeService into the adapter
Then the adapter records the [0.5, 1.0] backoff delays
And the test completes without a real sleep
```

## Edge Cases
- **Auth errors skip backoff**: If the completion error is an authentication error, then the adapter fails fast and records no sleep, because retrying a permanent error cannot succeed.
- **Time service absent**: If no time service is injected, then the adapter falls back to the real `time.sleep`, because the optional dependency keeps the constructor backward compatible.
- **Successful second attempt**: If the second attempt succeeds, then the adapter records a single 0.5 delay, because the retry loop stops after success.

## Key Unknowns
- [x] [Technical] Factory resolution safety: RESOLVED — the real composition registers `ITimeService`, and the root already resolves it for `SessionService` and `SessionPorts`. Design Sensitivity: if a partial container resolves `ILlmClient` without `ITimeService`, the factory change would raise; the integration gate confirms no such path exists.
- [x] [Technical] Recording double: RESOLVED — `register_mock` and `POSIXPathMock(spec=ITimeService)` are contract-bound and record sleeps through `side_effect`. The sibling `test_litellm_adapter_retries.py` already uses this pattern. Design Sensitivity: if a shared fake were required, the fix would touch the harness; the local double keeps the change scoped.
- [x] [Domain] Scope: RESOLVED — the user named the factory plus four tests. Design Sensitivity: any additional sleeping test stays out of this slice.

## Impact
1. `[MIGRATE]` `src/teddy_executor/registries/infrastructure.py` — pass `time_service=container.resolve(ITimeService)` into the `ILlmClient` factory.
2. `[MIGRATE]` `tests/suites/integration/adapters/outbound/test_llm_wiring.py` — assert the resolved adapter carries an `ITimeService`.
3. `[MIGRATE]` `tests/suites/unit/adapters/outbound/test_litellm_retries.py` — inject a recording `ITimeService` in `test_litellm_adapter_retries_on_ssl_error` and `test_litellm_adapter_exhausts_retries`, and assert the recorded backoff.
4. `[MIGRATE]` `tests/suites/unit/adapters/outbound/test_litellm_adapter.py` — inject a recording `ITimeService` in `test_get_completion_wraps_errors_in_llm_api_error`.
5. `[MIGRATE]` `tests/suites/unit/adapters/outbound/test_litellm_adapter_robustness.py` — inject a recording `ITimeService` in `test_get_completion_error_handling` and assert the recorded backoff.

## Deliverables
- [ ] **Wiring** - Inject `time_service=container.resolve(ITimeService)` into the `ILlmClient` composition factory and drive the composition-root boundary with an integration wiring assertion that the resolved adapter carries an `ITimeService`.
- [ ] **Migration** - Inject a recording `ITimeService` into the four named retry tests and assert the recorded `[0.5, 1.0]` schedule so no real backoff sleep remains.

## Implementation Notes

## Verification
1. **Retry tests run without real backoff:**
   Run `uv run pytest tests/suites/unit/adapters/outbound/test_litellm_retries.py tests/suites/unit/adapters/outbound/test_litellm_adapter.py::test_get_completion_wraps_errors_in_llm_api_error tests/suites/unit/adapters/outbound/test_litellm_adapter_robustness.py::test_get_completion_error_handling --durations=5`.
   Verify all four named tests pass and each completes in well under one second.
2. **Factory wiring:**
   Run `uv run pytest tests/suites/integration/adapters/outbound/test_llm_wiring.py`.
   Verify the time-service wiring assertion passes.
