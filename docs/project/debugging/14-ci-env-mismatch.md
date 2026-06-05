# Bug: CI fails despite local tests passing
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** [stability-and-bugfixes.md](/docs/project/specs/stability-and-bugfixes.md)

## Symptoms
- **Expected:** All tests pass in CI (matching local behavior).
- **Actual:** CI pipeline fails with `AssertionError` in `test_get_completion_calls_litellm_correctly` on all three OS (ubuntu, macos, windows).
- **Reproduction Steps:** Run `ci.yml` pipeline or run `pytest tests/suites/unit/adapters/outbound/test_litellm_adapter.py::test_get_completion_calls_litellm_correctly -p no:xdist -o "addopts="` locally (without xdist). The test will fail because the assertion expects no `timeout` parameter but the actual call includes `timeout=300`.

## Context & Scope
### Regressing Delta
Commit `fcfa37bb` ("feat(llm): add timeout default fallback (300s) to _prepare_completion_params") added a `timeout=300` default to `LiteLLMAdapter._prepare_completion_params()`. The test `test_get_completion_calls_litellm_correctly` was not updated to include `timeout` in its `assert_called_once_with` call.

### Environmental Triggers
- **CI Environment:** All three OS, Python 3.11, fresh install with `poetry install`.
- **Local Workaround:** The test passes locally when run with xdist (default `-n auto`) or when the global `litellm` mock state from a previous test run is still cached. Running without xdist reveals the failure.
- **Root Cause:** The assertion at line 61 of `test_litellm_adapter.py` expects `completion(model=..., messages=..., temperature=0.7)` but the actual call includes `timeout=300`.

### Ruled Out
- Parser resilience changes (commit 55de517e)
- Other litellm test files (telemetry, laziness, retries, robustness) — only one assertion affected.
- Windows TTY detection, Web Scraper, Context Service.
- The `timeout` parameter does **not** override user-specified timeouts; the guard `if "timeout" not in params:` ensures defaults only apply when no timeout is set.

## Diagnostic Analysis
### Causal Model
1. `_prepare_completion_params()` merges `llm` config, user kwargs, then sets `timeout=300` if not already present.
2. `get_completion()` calls `_prepare_completion_params()` and passes the merged params to `litellm.completion()`.
3. Test `test_get_completion_calls_litellm_correctly` calls `get_completion(model="gpt-4", messages=[...], temperature=0.7)`.
4. The test asserts `litellm.completion.assert_called_once_with(model=..., messages=..., temperature=0.7)` — **missing** `timeout=300`.
5. In CI, the mismatch causes `AssertionError`. Locally with xdist, the test passes due to mock state caching/call-history interference from the module-scoped `reset_litellm_mock` fixture.

### Discrepancies
- Local pass vs CI failure: The original test passes when run via `poetry run pytest` with xdist (default `-n auto`). This is a test isolation bug: the `reset_litellm_mock` autouse fixture resets the mock before each test, but xdist worker caching may preserve call history across runs. (Resolved: the probe file replicates the exact setup and demonstrates the same failure as CI when run in isolation without xdist interference.)

### Investigation History
1. CI logs extracted; failure is `litellm.completion` call missing `timeout=300`.
2. Regressing delta isolated to commit `fcfa37bb`.
3. Local reproduction attempts: original test passed with xdist. Probe in `spikes/` failed due to missing conftest. Probe in `tests/` succeeded in replicating the failure.
4. Probe confirmed `timeout=300` is present in call kwargs and assertion fails exactly like CI.
5. Systemic Audit: only one stale assertion in the litellm test suite.

## Solution
**Root Cause:** Commit `fcfa37bb` added a `timeout=300` default in `_prepare_completion_params` but the unit test assertion was not updated, causing CI failures on all platforms.

**Fix:** Add `timeout=300` to the `assert_called_once_with` call in `test_get_completion_calls_litellm_correctly` at `tests/suites/unit/adapters/outbound/test_litellm_adapter.py:61`.

**Redundant Regression Test Removed:** A dedicated regression test file (`test_bug_14_timeout_mismatch.py`) was initially created but failed on Windows CI because it did not inherit the `reset_litellm_mock` autuse fixture from `test_litellm_adapter.py`. Since the original test now includes `timeout=300` in its assertion, the separate file was redundant and was removed. The original test file provides adequate coverage.

**Preventative Measures:**
1. **Test-Regression Pairing:** When adding default parameters to shared internal methods (`_prepare_completion_params`), all tests that assert on the merged parameter set must be updated as part of the same commit. This could be enforced via code review checklist or a pre-commit hook that checks for symmetry between `_prepare_completion_params` default assignments and test assertions.
2. **Categorical Audit:** Search the test suite for `assert_called_once_with` patterns on methods that accept merged config parameters. Use `grep -rn "assert_called_once_with" tests/suites/unit/adapters/outbound/test_litellm_adapter.py` (already done — only one affected).
3. **Integration Test for Defaults:** Consider adding a dedicated test for `_prepare_completion_params` that validates all default parameters (timeout, model, api_key) are present, making the contract explicit and less likely to be missed.
