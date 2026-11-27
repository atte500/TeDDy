# Bug: Wiring Test Depends on a Process-Global Mock Counter
- **Status:** Resolved
- **Milestone:** [Runtime Reliability & Boundary Purity](../milestones/07-runtime-reliability.md)
- **Vertical Slice:** —
- **Specs:** —
## Symptoms
CI run [45980301696](https://github.com/atte500/teddy/actions/runs/45980301696) (commit `77280b66`, "Add MCP to FAQ") failed the blocking `Test Suite (macos-latest)` job. `tests/suites/integration/adapters/outbound/test_llm_wiring.py::test_validation_then_retry_wiring` reported:
```
E       AssertionError: Expected 2 completion calls but got 5
```
Fix-free reproduction attempts all pass: the test alone, the outbound unit plus integration directories, the acceptance suite plus the test, and the whole suite in one process (2795 passed, 5 skipped), as well as two default-xdist full runs (`-n auto --dist worksteal`, 2795 passed each).
The commit under test changes `README.md` only, so no production behaviour was altered.

Deterministic reproduction: seeding three calls on the shared double before the test body (`spikes/debug/litellm-call-count-leak/probe_seeded_counter.py`) fails the test with `Expected 2 completion calls but got 5`, matching the CI message exactly.
## Context & Scope
### Regressing Delta
None. The failing test was introduced by `41d27b68` ("feat(test): add wiring integration test for validation-then-retry flow") and the adapter was last functionally touched by `f1c1f0e0`. The triggering change is the docs-only `77280b66`.
### Environmental Triggers
The failure requires a pytest worker whose test composition differs from the local single-process collection order: CI runs `uv run pytest` with `addopts = ["-n", "auto", "--dist", "worksteal", "--import-mode=importlib", "--timeout=5"]`, so a worker receives tests dynamically and can execute a later-collected test before `test_llm_wiring.py`.
### Ruled Out
- **Adapter retry loop as a source of more than two calls.** `get_completion` returned the attempt-2 success object, which is only possible if the two-element `side_effect` list was consumed exactly twice: the loop made exactly two calls. The second call site, `_handle_hydration_retry` (line 759), is gated behind `_is_not_found_error` and is unreachable for `RuntimeError("Connection refused")`.
- **Outbound unit suites as the leak source.** `test_litellm_adapter.py` resets the shared mock in an autouse fixture, `test_litellm_adapter_retries.py` and `test_litellm_adapter_telemetry.py` inject a private `_litellm_provider`, and `test_litellm_retries.py` / `test_litellm_adapter_robustness.py` monkeypatch `litellm.completion` with plain callables that never touch the shared counter.
- **Preflight as a completion caller.** `validate_config` calls `validate_environment`, `get_llm_provider`, and — only when `include_remote` is set — `check_valid_key` through a `ThreadPoolExecutor`. None of these invoke `litellm.completion`.
## Diagnostic Analysis
### Causal Model
`tests/harness/setup/composition.py` installs one module-level `Mock()` as `sys.modules["litellm"]` for the whole pytest process, and nothing resets `litellm.completion`'s call history except `tests/suites/unit/adapters/outbound/test_litellm_adapter.py`'s module-local autouse fixture.
`test_validation_then_retry_wiring` asserts an absolute `litellm.completion.call_count == 2` on that process-global object. Because `unittest.mock` consumes a list-valued `side_effect` independently of `call_count`, calls recorded by any earlier test in the same worker inflate the counter while the test's own two scripted attempts still succeed and return the expected response.
Observed value `5` therefore decomposes as three inherited calls plus the test's own two. Which test supplies the three is immaterial to the defect: any test driving the container-resolved `LiteLLMAdapter` through the shared module mock moves the counter.
### Discrepancies
- [x] CI observed `call_count == 5` where 2 is expected (Resolved: the shared double already held three calls from earlier tests in the same worker, so the assertion reported worker scheduling rather than retry behaviour. Reproduced deterministically by seeding three calls via `spikes/debug/litellm-call-count-leak/probe_seeded_counter.py`).
- [x] Local single-process full suite stays green (Resolved: in default collection order `tests/suites/integration/**` runs before `tests/suites/unit/**`, and no test in that order leaves calls on the shared counter before the wiring test).
- [x] The counter-mutation plugin reported a single `LEAK` line and never printed its `FINAL` line (Resolved: the sample point was `pytest_runtest_teardown`, so a test that resets the counter and then makes an equal number of calls nets to zero. The setup-sampling probe closed that blind spot by sampling at setup too, and reported no local residue either).
- [x] The specific CI worker contributor of the three inherited calls is unidentified (Resolved as non-blocking: the harness reset removes the whole failure class, so the fix does not depend on the contributor's identity. The setup-sampling probe under the real xdist configuration found no local residue).
### Investigation History
1. Read the failing test and grepped every `litellm` reference; found the process-global mock in `tests/harness/setup/composition.py` and the single reset site in `test_litellm_adapter.py`. Concluded the assertion reads a shared counter.
2. Ran the test alone and in a combined outbound unit+integration run without `-n0`; both passed. Conclusion: invalid probe, because xdist split the files across workers and no state could accumulate.
3. Read the adapter's retry region and grepped its call sites; found one call in the retry loop and a hydration call at line 759 gated behind `_is_not_found_error`. Concluded the plain retriable path cannot exceed `max_retries` calls.
4. Replayed session-orchestration plus the wiring test and then acceptance plus the wiring test with `-n0`; both passed. Combined with the default collection order (acceptance, integration, unit), concluded fixed-order replays cannot reproduce a load-balanced co-location.
5. Ran the full suite in one process with a teardown-sampling counter plugin; observed a single line, `LEAK ...test_validation_then_retry_wiring +2 total=2`, no `RESET`, no `FINAL`. Conclusion: no test in default order leaves calls behind, but the instrument is blind to reset-then-call patterns and its coverage is unverified.
6. Noted that list-valued `side_effect` consumption is independent of `call_count` and that the test received the attempt-2 response, deducing the loop made exactly two calls while the counter held five → three calls preceded the test body.
7. Listed CI runs, identifying the failing run `45980301696` for commit `77280b66`; ran the default-xdist suite twice locally (2795 passed each). Conclusion: the failure is rare and requires the CI worker composition.
8. Read `get_completion` end to end for the first time without tail truncation; confirmed the loop returns the attempt-2 response and that `_prepare_completion_params`/`validate_config` issue no completion calls. Conclusion: the two scripted attempts succeeded, so the loop made exactly two calls and the counter held three before the test body ran.
9. Created the case file and pulled the failing step log for run `45980301696`; the log shows `[gw1] darwin -- Python 3.14.10` and the identical assertion. Conclusion: the failure is a worker-local accumulation, and the environment is not otherwise implicated.
10. Built the seeded MRE (`probe_seeded_counter.py`), recording three calls on the shared double before the test body; the production test failed with `Expected 2 completion calls but got 5`, matching CI byte-for-byte. Conclusion: the mechanism is observed fact, not inference, and the contributor's identity is unnecessary to the diagnosis.
11. Proved the fix in the sandbox: `replica_test_llm_wiring.py` mirrors the production arrange phase plus the reset and passes under the same seeding, while the unmodified production test still fails under it. Then applied the fix to the harness — `reset_shared_litellm_double()` in `tests/harness/setup/composition.py`, registered as an autouse fixture in `tests/conftest.py` — added `tests/suites/unit/test_shared_litellm_double_isolation.py`, and verified: the previously failing seeded run passes, the new regression test passes, and `make test` reports 2798 passed, 5 skipped.
12. Audited the fix for the very defect class it removes by grepping every assignment to the double's child return values; found `test_litellm_adapter.py` swapping `litellm.completion.return_value` at lines 24, 35, and 98. Conclusion: `reset_mock(return_value=False)` would let those survive, so the new canonical-response assertion was order-dependent as first written. Hardened the reset to reassert the harness's return values through a single `_install_default_return_values()` installer, rewrote the regression test to leak a return value and assert the restore, documented the seam, and verified: the adapter module run immediately before the isolation tests in one process passes (23 passed), and `make test` still reports 2798 passed, 5 skipped.

## Solution
### Root Cause
Verified. `tests/harness/setup/composition.py` installs one `Mock()` as `sys.modules["litellm"]` for the whole pytest session. `test_validation_then_retry_wiring` asserts the absolute `litellm.completion.call_count == 2` on that process-global object, so any earlier test in the same xdist worker that drives the container-resolved `LiteLLMAdapter` through the shared double inflates the counter, and the assertion reports worker scheduling instead of the retry behaviour under test. `unittest.mock` consumes a list-valued `side_effect` independently of `call_count`, which is why the test still received its attempt-2 response while the counter read 5.

The fix was applied directly to the harness, within the small-change bound (harness module plus root conftest plus one regression test, no production code, suite fully green):

- `reset_shared_litellm_double()` in `tests/harness/setup/composition.py` owns the reset beside the state it clears: call history and every child `side_effect` are cleared recursively, then the harness's own return values are reasserted from the single `_install_default_return_values()` installer. The reassert is the second half of the same defect, not polish: `reset_mock(return_value=False)` deliberately leaves swapped responses in place, and `test_litellm_adapter.py` (lines 24, 35, 98) assigns `litellm.completion.return_value`, so a partial reset would have made the new canonical-response assertion order-dependent in exactly the way this case file exists to remove.
- `tests/conftest.py` registers it as an autouse fixture bracketing every test. Registration must live in a conftest: pytest only honours fixtures declared there or in plugin modules, so a fixture defined inside `composition.py` is never collected.
- `tests/suites/unit/test_shared_litellm_double_isolation.py` guards the seam permanently: a scripted failure is cleared, a swapped return value is restored to the canonical plan response, and every test body starts clean.

Evidence, all preserved under `spikes/debug/litellm-call-count-leak/`:
- `probe_seeded_counter.py` — MRE; with three seeded calls the production test fails `Expected 2 completion calls but got 5`, reproducing CI.
- `replica_test_llm_wiring.py` — sandbox proof; same arrange phase plus the reset passes under identical seeding, without touching `tests/`.
- The two throwaway instrumentation plugins (one reporting per-test counter deltas, one sampling the counter at setup as well as teardown) established the blind spots of teardown-only sampling and found no local residue. They were deleted once the diagnosis closed; their findings are recorded in the investigation history above.

### Affected Components
- `tests/suites/integration/adapters/outbound/test_llm_wiring.py`: unchanged; its absolute count assertion becomes truthful once every test starts from a clean double.
- `tests/harness/setup/composition.py`: now owns `reset_shared_litellm_double()` alongside the double whose state it resets.
- `tests/conftest.py`: imports the helper and registers the autouse fixture.
- `tests/suites/unit/test_shared_litellm_double_isolation.py`: new regression test for the harness seam.
- Consumers of the shared double (`test_litellm_adapter.py`, `test_litellm_adapter_retries.py`, `test_litellm_adapter_preflight.py`, `test_litellm_adapter_telemetry.py`): unaffected, because each scripts its own behaviour after the reset. `test_litellm_adapter.py` assigns `litellm.completion.return_value`, which the canonical reset now discards at the next test boundary instead of leaking onward.
- `docs/architecture/tests/setup/composition.md`: records the `canonical_double_per_test` invariant and replaces the claim that the `os.killpg` guard is active with `killpg_poka_yoke_inactive`, because pytest never collects a fixture declared in that module.

### Follow-ups
Out-of-scope debts surfaced during the investigation, recorded as Requirement 13 in [Runtime Reliability & Boundary Purity](../milestones/07-runtime-reliability.md):
- `guard_os_killpg` in `tests/harness/setup/composition.py` is an autouse fixture that pytest never collects, so the `os.killpg` protection it documents is not in force. It needs the same conftest registration this fix just demonstrated.
- `test_validation_then_retry_wiring` builds `Mock(spec=IConfigService)` directly instead of the harness mock-registration helper, which diverges from the mock-binding rule and was the reason the test also left an exhausted list `side_effect` behind.
