# Bug: Test Suite Slower on Windows Than macOS
- **Status:** Resolved
- **Milestone:** N/A (ad-hoc)
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
The full `make test` run takes substantially longer on Windows 11 than on macOS. The user reports that certain tests in particular seem very slow. Expected behavior is comparable wall-clock time across platforms for the same serial test work.

## Context & Scope
### Regressing Delta
No single regressing commit. The slowdown is platform-conditional. The pytest-httpserver default host (`localhost`) interacts with the Windows IPv6-first loopback connect path. Four litellm retry tests also pay real backoff sleeps on every platform.

### Environmental Triggers
- Windows 11 host with `cmd.exe` as the default shell.
- `pytest` addopts in `pyproject.toml`: `-n auto`, `--import-mode=importlib`, `--timeout=5`.
- CI raises the pytest timeout to 15s when `CI=true`.

### Ruled Out
- DNS and `getaddrinfo` cost, which is 0ms for both `localhost` and `127.0.0.1`.
- Proxy resolution, because IP-addressed requests complete in 2-3ms under the same default environment.
- Server handling and fixture startup, which cost 9-10ms and answer IP requests in 2ms.
- pyfakefs setup cost, which is 3ms per cycle and affects only 33 test functions.
- Cold `litellm` import per worker. The harness replaces `sys.modules["litellm"]` with a Mock before any test imports it, and `trafilatura` is never loaded, so the 3.57s figure measured outside pytest never appears in suite wall-clock time.

## Diagnostic Analysis
### Causal Model
Measured on this Windows 11 host (12 logical CPUs, Python 3.12.9). Fixed per-worker costs are real but bounded: twelve workers each pay a cold `litellm` import near 3.57s, `trafilatura` 0.61s, `mistletoe` 0.25s, and one `git status --porcelain` shell-out near 40ms. Per-test autouse work is negligible near 0.15ms. The pyfakefs term is 3ms per cycle after the first cycle and only 33 test functions request the `fs` fixture, so pyfakefs is not a suite-scale cost and the earlier 0.79s reading was cold-import overhead. The dominant per-test cost is a single fixed wait near 2.0s attached to each real loopback HTTP request addressed by hostname. Every openrouter test that issues one request costs 2.02-2.06s, while the two cache-hit tests that start the same `httpserver` fixture without issuing a request cost 0.01s, which places the cost in the request and not in the fixture. On the same server port, a raw socket connect to `localhost` costs 2035-2057ms while the identical connect to `127.0.0.1` costs 0ms, `getaddrinfo` costs 0ms for both hosts, and `urllib` plus `requests` reproduce the split, so the cost is the hostname connect path rather than name resolution, transport, or server handling. The pytest-httpserver plugin resolves its listen host from the `PYTEST_HTTPSERVER_HOST` environment variable and falls back to `localhost` (`HTTPServer.DEFAULT_LISTEN_HOST`), and `url_for` interpolates the constructed host into every served URL. No `--httpserver-host` flag exists, so the environment variable is the only override. The raw resolver order is `::1` before `127.0.0.1`, the server binds IPv4 only, and constructing the server with `host="127.0.0.1"` collapses a request from 2037ms to 1ms. Four litellm retry tests pay exactly 1.50s because the adapter computes `delay = 0.5 * (2**attempt)` in `_should_retry_completion` and the tests never inject a time service, so three attempts sleep 0.5s then 1.0s on real `time.sleep`. Together these 19 tests carried roughly 36s of the 40.87s serial run of 296 tests.

The remedy is verified end to end. Pinning `PYTEST_HTTPSERVER_HOST=127.0.0.1` in `tests/conftest.py` collapsed the two formerly slow modules from 31.37s to 0.40s. An A/B run of the full suite measured 45.87s with the old `localhost` default against 28.93s with the pin, a suite-level delta of 16.94s on this host. The serial outbound subset fell from 40.87s to 8.95s. The four litellm tests at 1.50s each are the only remaining serial wait. That wait is platform-independent, and a paired spike measured 1.50s on the real clock against 0.00s with a recording `ITimeService` fake that captured the `[0.5, 1.0]` backoff schedule. The `ILlmClient` factory in `registries/infrastructure.py` does not pass `time_service`, while `SessionService` and `SessionPorts` receive it, so container-resolved litellm tests also sleep on the real clock.

### Discrepancies
- [x] The 0.79s pyfakefs cycle was thought to be per-test (Resolved: five repeated cycles average 3ms; the 0.79s reading was first-cycle import cost, and only 33 tests request `fs`).
- [x] Same serial test work is expected to cost similar wall-clock time on both platforms, but Windows is reported much slower (Resolved: the Windows-specific term is the IPv6-first loopback stall, measured at 16.94s of suite wall-clock and 31.92s of the serial outbound subset; the litellm backoff sleeps are real on both platforms, and the import term does not apply because the harness mocks the heavy libraries).
- [x] The 2.0s openrouter cost is the hostname connect path (Resolved: the resolver returns `::1` before `127.0.0.1`, the server binds IPv4 only, and pinning the server host to `127.0.0.1` collapses a request from 2037ms to 1ms).
- [x] The 1.50s litellm cost is confirmed as two real backoff sleeps (Resolved: `_should_retry_completion` computes `delay = 0.5 * (2**attempt)`, and the four named tests never inject `ITimeService`).
- [x] pytest-httpserver exposes its host override through the `PYTEST_HTTPSERVER_HOST` environment variable, and `url_for` interpolates the constructed host (Resolved: there is no `--httpserver-host` CLI flag; the constructor host and the environment variable both change served URLs).
- [x] A two-request test would cost about 4s against the 5s per-test timeout, so this wait may also be a latent flake source (Resolved: the pin removes the per-request stall, so every request completes in milliseconds and the latency budget no longer approaches the timeout).

### Investigation History
1. Read `docs/templates/case-file.md`, `Makefile`, `pyproject.toml`, and `tests/conftest.py`. Found `-n auto` parallelism, a 5s per-test timeout, and several autouse fixtures, including a session-scoped fixture that shells out to `git status --porcelain`.
2. A `git grep` inventory attempt failed because `head` does not exist in `cmd.exe`. Switched to portable commands without POSIX pipes.
3. Inventoryed sleeps and explicit timeouts across `tests/`. Real `time.sleep` calls appear in the acceptance hanging-command tests, the concurrent-suppression tests, and the quit-key listener tests. The litellm retry unit tests patch `time.sleep`, so their recorded delay lists are mock assertions rather than real waits.
4. Measured per-worker startup costs with `spikes/debug/windows-test-suite-slowness/00-baseline-probe.py`. Cold `litellm` import 3.57s, `trafilatura` 0.61s, `mistletoe` 0.25s, `textual` 0.04s, `find_project_root` 0.15ms per call, `git status --porcelain` 40ms, pyfakefs `Patcher` cycle 0.79s. Concluded that session-level git and project-root work is negligible while imports and pyfakefs are material.
5. Ran `tests/suites/unit/adapters/outbound` serially (`-n 0`): 296 passed, 17 skipped, 40.87s. Durations show 15 openrouter hydrator/harness tests at 2.02-2.08s each and four litellm error/retry tests at 1.50s each, together accounting for roughly 36s of the run.
6. Counted fixture usage across all test modules with `spikes/debug/windows-test-suite-slowness/01-cost-attribution.py`. The `fs` fixture is requested by 33 test functions, `env` by 160, `container` by 161, `openrouter_mock` by 7, and `httpserver` by 12. Measured spawn costs at 11.1ms for `cmd /c echo` and 41.7ms for a Python interpreter, and measured the pyfakefs `Patcher` cycle at 3ms across five cycles, which retires the earlier 0.79s reading as cold-import cost.
7. Re-ran the two openrouter modules serially with `--durations=25`. All 22 tests cost 2.02-2.06s in the call phase, and one teardown cost 0.55s. The two cache tests that use `httpserver` without issuing a request cost 0.01s. This places the 2.0s cost in the loopback HTTP request rather than in the fixture.
8. Ran `spikes/debug/windows-test-suite-slowness/02-loopback-http-cost.py`. On the same pytest-httpserver port, a raw connect to `localhost` cost 2035-2057ms while `127.0.0.1` cost 0ms. `getaddrinfo` cost 0ms for both hosts, and `urllib` plus `requests` reproduced the split. Every server log line records `127.0.0.1`, so the fixture listens on IPv4 only. The probe then died on `requests.get(..., trust_env=False)` because that keyword belongs on a `Session`.
9. Ran `spikes/debug/windows-test-suite-slowness/03-host-override-inspection.py`. The installed package exposes `HTTPServer(host="localhost")`, its plugin reads `PYTEST_HTTPSERVER_HOST`, and `url_for` interpolates `self.host`. The raw resolver order is `['::1', '127.0.0.1']`. A `localhost` URL cost 2037ms while a `127.0.0.1` URL cost 1ms on the same port. Passing `--httpserver-host=127.0.0.1` failed with `unrecognized arguments`, which proves the environment variable is the only override.
10. Ran `spikes/debug/windows-test-suite-slowness/04-time-service-retry-proof.py`. The identical three-attempt failure path cost 1.50s with the real clock and 0.00s with a recording fake, and the fake recorded sleeps of `[0.5, 1.0]`, which matches `delay = 0.5 * (2**attempt)`.
11. Applied `os.environ.setdefault("PYTEST_HTTPSERVER_HOST", "127.0.0.1")` in `tests/conftest.py` and added an IPv4-literal assertion to `test_openrouter_mock_fixture`. The two formerly slow modules passed in 0.40s, and the full suite passed 1824 tests in 28.93s.
12. Ran the full suite with `PYTEST_HTTPSERVER_HOST=localhost` as the counterfactual. It took 45.87s and failed only the new assertion. That single failure confirms both the 16.94s suite-level cost of the stall and that the regression guard fires when the pin is missing. Re-ran the serial outbound subset at 8.95s against the 40.87s baseline, where the four litellm retry tests at 1.50s each were the only remaining serial wait.
13. Audited the heavy-import claim: `sys.modules["litellm"]` is a `unittest.mock.Mock`, `trafilatura` is not loaded, and the real litellm module object has no `__file__`. The suite never imports the real libraries, so the spawn and import terms do not contribute to suite wall-clock. Grepped the composition root: `time_service=container.resolve(ITimeService)` appears for `SessionService` and `SessionPorts` but is absent from the `ILlmClient` factory.

## Solution
### Root Cause
The slowdown is the interaction between the pytest-httpserver default listen host and the Windows dual-stack loopback path. The server binds the IPv4 literal only, while `localhost` resolves to `::1` first on Windows. Every request addressed by hostname therefore wastes about two seconds on a failed IPv6 connect before the IPv4 fallback answers. The 19 openrouter tests that issue a request carried roughly 36s of the 40.87s serial outbound subset, and the 22-test openrouter module pair fell from 31.37s to 0.40s once the host was pinned. The Windows-specific suite delta is 16.94s, measured as 45.87s against 28.93s in an A/B run. A second wait is platform-independent: four litellm retry tests never inject `ITimeService`, so three attempts sleep the real 0.5s and 1.0s backoff. The loopback fix was applied directly, touching `tests/conftest.py` and its matching test file. The litellm backoff fix was proven in a sandbox spike (`spikes/debug/windows-test-suite-slowness/04-time-service-retry-proof.py`), which showed 1.50s on the real clock against 0.00s with a recording fake and a captured schedule of `[0.5, 1.0]`. That fix spans three test files and remains a Developer handoff.

### Affected Components
- `tests/conftest.py`: Added the `PYTEST_HTTPSERVER_HOST=127.0.0.1` pin. Every test that requests the `httpserver` or `openrouter_mock` fixture now receives an IPv4-literal URL.
- `tests/suites/unit/adapters/outbound/test_openrouter_harness.py`: Added the IPv4-literal assertion that guards the pin.
- `tests/suites/unit/adapters/outbound/test_openrouter_hydrator.py`: Ten tests now complete in milliseconds instead of about 2s each. No source change was required.
- `src/teddy_executor/registries/infrastructure.py`: The `ILlmClient` factory must pass `time_service=container.resolve(ITimeService)` so container-resolved litellm tests stop sleeping on the real clock.
- `tests/suites/unit/adapters/outbound/test_litellm_retries.py`: Two retry tests must inject a recording `ITimeService` fake.
- `tests/suites/unit/adapters/outbound/test_litellm_adapter.py`: `test_get_completion_wraps_errors_in_llm_api_error` must inject a recording `ITimeService` fake.
- `tests/suites/unit/adapters/outbound/test_litellm_adapter_robustness.py`: `test_get_completion_error_handling` must inject a recording `ITimeService` fake.
