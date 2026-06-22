# Bug: `teddy update` reports network error despite working network

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** [N/A]
- **Specs:** [docs/project/specs/update-checker.md](/docs/project/specs/update-checker.md)

## Symptoms

**Expected:** When running `teddy update` with a working network connection, the command should either upgrade to the latest version or report that the latest version is already installed.

**Actual:** The command immediately fails with "Could not check for updates: network error." despite the network being functional.

**Reproduction Steps:**
1. Have a working internet connection.
2. Run `teddy update` on a system where TeDDy is installed.
3. Observe the error message.

## Context & Scope

### Regressing Delta
The bug is not a code regression — the `update_checker.py` module was introduced in the [00-02-update-checker](/docs/project/slices/00-02-update-checker.md) slice and has always used silent error catching for `fetch_latest_version()`. The triggering condition is the macOS Python 3.14 framework installation, which lacks proper SSL certificate configuration. The codebase's use of `urllib.request.urlopen` without an explicit SSL context causes SSL verification to fail on Python 3.14, and the generic `except` block converts this to a non-specific `None` return, resulting in the "network error" message.

### Environmental Triggers
- **macOS Python 3.14 framework build**: The Python.org installer for macOS does not bundle `certifi` or configure SSL certificates properly. This affects any HTTPS request made via `urllib.request.urlopen` without an explicit `ssl.create_default_context(cafile=...)`.
- **`uv tool install`**: The package is installed via `uv tool install teddy-cli`, which places it under the Python 3.14 framework. The dev venv uses Python 3.11 installed via Homebrew or pyenv, which has working SSL certs.
- **Python 3.11 dev venv**: The SSL probe succeeded using Python 3.11 (dev environment), confirming the network itself works.

### Ruled Out
- **Network connectivity**: Direct `curl` and urllib requests to google.com and pypi.org succeed from the same machine.
- **Code logic errors**: `fetch_latest_version()` is structurally correct — it works in Python 3.11. The error is external (SSL cert configuration).
- **Cache corruption**: Deleted/recreated cache does not affect the error.
- **API key or proxy configuration**: Not relevant — the update check uses direct HTTPS to PyPI.

## Diagnostic Analysis

### Causal Model
1. User runs `teddy update` on a macOS system where TeDDy is installed via `uv tool install teddy-cli`.
2. The installed binary uses the macOS Python 3.14 framework (`/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14`).
3. Python 3.14's `urllib.request.urlopen` uses default SSL context, which attempts to verify certificates against the system CA bundle.
4. The Python 3.14 framework build on macOS does not have `certifi` installed and its default SSL context cannot find the system root certificates (the `_ssl` module's `get_default_verify_paths()` returns incorrect paths).
5. `fetch_latest_version()` calls `urllib.request.urlopen(req, timeout=10)`, which raises `SSL: CERTIFICATE_VERIFY_FAILED`.
6. The `except (urllib.error.URLError, OSError, json.JSONDecodeError, KeyError): return None` block catches the `URLError` (wrapping the `SSLError`) and silently returns `None`.
7. `__main__.py` checks `if latest is None:` and prints "Could not check for updates: network error." — a misleading message that does not indicate the actual SSL certificate problem.

### Discrepancies
1. `fetch_latest_version()` catches SSL errors and returns None, but the error is not SSL-unrelated — it's cert-related. (Resolved: The actual exception is `URLError` wrapping `SSLError`, which is caught by the `urllib.error.URLError` handler. The fix should either log the real error or use an explicit SSL context with `certifi`.)
2. The error message "network error" suggests a generic network failure, but the actual problem is SSL certificate configuration. (Resolved: The message is misleading because the root cause is not network connectivity but SSL cert validation. The fix should provide a more specific error or resolve the SSL issue gracefully.)

### Investigation History
1. **Gather context**. Read `__main__.py`, `update_checker.py`, `cli_helpers.py`. Identified the error path: `fetch_latest_version()` returns None → "network error". Installed version is 0.1.3, PyPI has 0.1.4. Conclusion: Code path understood, need to reproduce.
2. **Create MRE**. Created `spikes/debug/07-update-mre.py` that calls `fetch_latest_version()` directly. In dev venv (Python 3.11), it succeeds: returns "0.1.4". Installed `teddy` binary uses Python 3.14. Conclusion: Bug is environment-specific (dev passes, installed fails).
3. **Reproduce bug**. Ran `teddy update` → "Could not check for updates: network error." Confirmed. Inspected binary: `file` says `/Library/Frameworks/Python.framework/Versions/3.14/bin/teddy` is a Python 3.14 script. Probed Python 3.14 directly: `urllib.request.urlopen` to PyPI fails with `SSL: CERTIFICATE_VERIFY_FAILED`. Conclusion: Root cause is SSL certificate verification failure in macOS Python 3.14 framework build.
4. **Verify network works**. Basic connectivity test (google.com, curl) succeeds from same environment. Conclusion: Network is functional; error is SSL-specific.
5. **Identify fix path**. The Python 3.14 framework lacks `certifi` in its bundle. The fix is to use `ssl.create_default_context(cafile=certifi.where())` when `certifi` is available, or to fall back to `ssl._create_unverified_context()` with a log warning. Additionally, `perform_upgrade` must detect uv-installed packages and use `uv tool upgrade` instead of pip.

## Solution

### Root Cause
The bug had two layers:

1. **SSL Certificate Verification Failure (direct cause):** `fetch_latest_version()` used `urllib.request.urlopen(req, timeout=10)` without an explicit SSL context. On macOS Python 3.14 framework builds (installed via Python.org installer), the default SSL context cannot locate system root certificates, raising `SSL: CERTIFICATE_VERIFY_FAILED`. The error was caught by the generic `except (urllib.error.URLError, ...)` block and converted to a silent `None` return.

2. **Silent Error Swallowing (propagation):** The `except` block did not log the actual exception, making the true cause invisible. The caller then displayed the misleading "network error" message.

3. **UV Tool Incompatibility (upgrade path):** `perform_upgrade()` used `sys.executable -m pip install --upgrade`, which fails when the package is installed via `uv tool install`. The upgrade command must use `uv tool upgrade teddy-cli` for uv-installed packages.

### Proven Fix
The fix was verified via a shadow file (`spikes/debug/shadow_update_checker.py`) that passed on both Python 3.14 (installed environment) and Python 3.11 (dev environment). The production file `src/teddy_executor/core/services/update_checker.py` was updated with:

| Change | Description |
|--------|-------------|
| **`_create_ssl_context()`** | New function that attempts to use `certifi.where()` as the CA bundle for SSL context creation. Falls back to default SSL context if `certifi` is unavailable. |
| **SSL context in `fetch_latest_version()`** | Calls `_create_ssl_context()` and passes it as `context=` to `urllib.request.urlopen()`. |
| **Improved error logging** | The `except` block now logs the actual exception via `logger.debug()` before returning `None`. |
| **`_is_uv_installed()`** | New function that checks `uv tool list` output to detect if `teddy-cli` was installed via uv. |
| **`_get_install_method()`** | Returns `"uv"` or `"pip"` based on uv detection. |
| **`perform_upgrade()`** | Now detects the install method and uses `uv tool upgrade teddy-cli` for uv installations, falling back to `pip install --upgrade` for traditional installations. |

### Preventative Measures
1. **Always provide explicit SSL context for HTTPS requests.** The `_create_ssl_context()` pattern should be used for any future HTTP calls in the codebase.
2. **Log before swallowing.** The improved error logging ensures that future network failures are debuggable without changing the user-facing behavior.
3. **UV detection as a reusable pattern.** The `_is_uv_installed()` function can be used by any component that needs to adapt behavior based on the installation method.
4. **Systemic audit performed:** All `urlopen` calls in the production codebase were audited (only one exists, now fixed). Broad error suppression patterns were documented as technical debt in `docs/project/PROJECT.md`.

### Files Modified
- `src/teddy_executor/core/services/update_checker.py` (production fix)
- `tests/suites/unit/core/services/test_bug_07_update_network_error.py` (new regression test, 11 tests)
- `tests/suites/unit/core/services/test_update_checker.py` (fixed 3 existing tests that broke due to uv detection addition)
- `docs/project/debugging/07-update-network-error.md` (this case file)
- `docs/project/PROJECT.md` (resolved uv debt, added silent error swallowing debt)
