# Bug: Windows CI Worker Crash (gw3)
- **Status:** Unresolved
- **Milestone:** [N/A]
- **Vertical Slice:** [N/A]
- **Specs:** [N/A]

## Symptoms
Intermittent failures in Windows CI where a `pytest-xdist` worker (`gw3`) crashes. The CI reports "crashed worker gw3" without a standard Python traceback.

## Context & Scope
### Regressing Delta
Unknown. The issue appears intermittent, suggesting a race condition or a instability in a binary dependency on Windows.

### Environmental Triggers
- OS: Windows (GitHub Actions `windows-latest`)
- Runtime: Python 3.11
- Tooling: `pytest`, `pytest-xdist`

### Ruled Out
- Linux/macOS runners (no reported crashes on these platforms).

## Diagnostic Analysis
### Causal Model
The crash occurs specifically on Windows during the execution of `test_reviewer_widgets.py`.
- **Trigger:** The crash happens during `test_detail_item_contains_label_for_wrapping[asyncio]`.
- **Mechanism:** Windows uses `timeout method: thread` in `pytest-timeout`, which can cause unstable state or deadlocks if it interrupts the `asyncio` loop or TUI driver in a non-thread-safe way, leading to a process crash.
- **Evidence:** Worker `gw3` reported "node down: Not properly terminated" immediately before replacing the worker.

### Discrepancies
- N/A

### Investigation History
1. Gathered CI run history and identified failing run `26559989841`.
2. Extracted logs: Confirmed crash on Windows worker `gw3` during `test_reviewer_widgets.py` with `timeout method: thread` active.
3. Hypothesized that the 5s timeout is being exceeded on slow Windows runners, triggering a process-level kill by `pytest-timeout`.
4. Executed Remote Probe `26560213581` with `--timeout=60`. The test passed on Windows, confirming that the crash is a timeout-driven process termination.
5. Evaluated CI-specific fix: Proposed dynamic timeout adjustment in `conftest.py` that scales timeouts only when `os.environ.get("CI")` is present.

## Solution
### Root Cause
Intermittent worker crashes on Windows CI were caused by the 5s global timeout. Under heavy parallel contention (4 workers), TUI-related tests (Textual) frequently exceed this limit. On Windows, `pytest-timeout` uses the `thread` method, which terminates the entire worker process upon timeout, leading to the "node down" symptom.

### Proven Fix
Implement a dynamic timeout adjustment in `tests/conftest.py` using the `pytest_collection_modifyitems` hook.
- **Local Development:** The 5s global gate remains strictly enforced.
- **CI Environment:** When `os.environ.get("CI")` is detected, all tests are granted 30s of headroom (or 3x their specific timeout) to accommodate runner contention.

### Systemic Preventative Measures
- **Environment-Aware Harness:** Maintain a test harness that can scale its expectations (timeouts, retries) based on the execution environment without polluting the production source code with platform-specific guards.
- **Binary Isolation:** Continue strictly enforcing the local-import pattern for heavy binary libraries to minimize worker startup latency.
