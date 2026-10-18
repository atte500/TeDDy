# Slice: Litellm Retry Time-Service Injection
- **Status:** Completed
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
- [x] **Wiring** - Inject `time_service=container.resolve(ITimeService)` into the `ILlmClient` composition factory and drive the composition-root boundary with an integration wiring assertion that the resolved adapter carries an `ITimeService`.
- [x] **Migration** - Inject a recording `ITimeService` into the four named retry tests and assert the recorded `[0.5, 1.0]` schedule so no real backoff sleep remains.

## Implementation Notes

### Wiring (factory injection and composition-root assertion)
- The deliverable added `test_litellm_adapter_is_wired_with_time_service` to `tests/suites/integration/adapters/outbound/test_llm_wiring.py`. The test resolves `ILlmClient` from the harness `container` fixture and asserts that `llm_client._time_service` satisfies the `ITimeService` Protocol, mirroring the file's existing `_hydrator` assertion pattern.
- The Red step failed exactly as predicted: `assert False = isinstance(None, ITimeService)` with `None = ...LiteLLMAdapter object ... ._time_service`. That proved the factory omitted the dependency and left the private attribute unset.
- The Green step added one keyword argument, `time_service=container.resolve(ITimeService)`, to the single `ILlmClient` factory lambda in `src/teddy_executor/registries/infrastructure.py`. The wiring file then reported `4 passed in 3.90s`, covering the new assertion plus the three pre-existing wiring scenarios.
- The container fixture registers `ITimeService` as a transient `SystemTimeAdapter`, so `container.resolve(ITimeService)` never raises on the real composition path. No harness change was required.
- The Refactor sub-step found nothing to change. The production edit is one additive keyword argument, and the new test follows the file's existing assertion idiom.
- The Integration gate reported `1825 passed, 36 skipped in 29.08s`, which is the prior 1824 baseline plus the new wiring test. No existing consumer regressed.
- `test_validation_then_retry_wiring` stays unchanged and still pays one real 0.5s sleep. It now sleeps through the injected `SystemTimeAdapter.sleep` instead of the constructor fallback, so its behavior is identical.

### Migration (recording time service in the four named tests)
- The deliverable repaired `mock_time_service` in `tests/harness/setup/mocks.py`. The old body captured `original_sleep = mock.sleep` and then called it inside its own `side_effect`, which re-enters the same side effect without bound. The repaired body only appends the delay, so recording never recurses.
- The fixture was defined but unreachable. A `git grep` census found exactly one occurrence, its own definition. The deliverable re-exported it through `tests/harness/setup/composition.py` and imported it into the `tests/conftest.py` fixture surface and `__all__`, so tests resolve it like every other harness mock.
- The three manually constructed adapters in `test_litellm_retries.py` (two tests) and `test_litellm_adapter.py` (one test) now receive `time_service=mock_time_service` directly. The container-resolved `test_get_completion_error_handling` requests the fixture, which registers `ITimeService` in the container before `container.resolve(ILlmClient)` runs, so the factory returns the recording mock.
- Each of the four tests now asserts `mock_time_service.sleep_calls == [0.5, 1.0]`. The backoff contract therefore stays verified as an explicit assertion rather than being dropped for speed.
- The stale comment in `test_litellm_adapter_exhausts_retries` that predicted a future retry count was removed, because the retry count is now real.
- The Red baseline measured each of the four tests at exactly 1.50s, which is the two real backoff sleeps. The Green run reported `4 passed in 0.39s`, and every named test call-phase duration fell under 0.005s.
- The Integration gate reported `1825 passed, 36 skipped`, equal to the prior baseline because no test was added, only migrated.
- `test_validation_then_retry_wiring` remains unchanged and still pays one real 0.5s sleep through the injected `SystemTimeAdapter`. It is outside the four named tests.
- Debt: `test_litellm_adapter_retries.py` carries its own recording helper (`_create_adapter` with `_track_sleep`) that duplicates the shared fixture. Consolidating it would touch a shared harness file outside this slice, so it is recorded for Milestone 6.
- The delivery commit first failed at the `detect-secrets` hook, which flagged four fake-key fixture lines in the two staged litellm test files. Those strings are test data, not credentials. The remedy added the repo-standard `# pragma: allowlist secret` comment to every un-pragma'd occurrence of each fake value, because the hook deduplicates by file and hash and one pragma can promote the next occurrence.
- Adding the pragma to the single-line `get_completion` call that carries the fake caller key pushed it past the formatter width, so `ruff-format` reflowed the call and stranded the pragma on the closing bracket line. `detect-secrets` scans line by line, so the stranded pragma no longer covered the secret value. The remedy split the call one argument per line with a trailing comma and moved the pragma onto the `api_key` argument, and every hook then passed cleanly.
- This note names the fake key generically rather than quoting it. The same secret hook scans Markdown artifacts, so quoting a literal fake value here re-opens the gate it documents.

### Verification (quality audit and full-suite gate)
- The production double audit found no skeleton response, hardcoded delay, or temporary stub in the retry path. Every recorded delay derives from the shipped `0.5 * 2**attempt` formula, and the real `time.sleep` runs only on the documented no-time-service fallback.
- The upstream census confirmed the composition factory is the single production construction site that injects `time_service`. The four named tests plus the wiring assertion are the only slice consumers, and no orphaned helper remains.
- The full-suite gate reported `1825 passed, 36 skipped`, equal to the committed baseline, so the slice introduces no regression.

## Verification
1. **Retry tests run without real backoff:**
   Run `uv run pytest tests/suites/unit/adapters/outbound/test_litellm_retries.py tests/suites/unit/adapters/outbound/test_litellm_adapter.py::test_get_completion_wraps_errors_in_llm_api_error tests/suites/unit/adapters/outbound/test_litellm_adapter_robustness.py::test_get_completion_error_handling --durations=5`.
   Verify all four named tests pass and each completes in well under one second.
2. **Factory wiring:**
   Run `uv run pytest tests/suites/integration/adapters/outbound/test_llm_wiring.py`.
   Verify the time-service wiring assertion passes.
