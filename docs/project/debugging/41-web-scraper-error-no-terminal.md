# Bug: Error message after failed URL read should not be logged to terminal

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

When a READ action fails to fetch a URL (e.g., 404 Client Error), the error message "Failed to fetch URL '<url>': <error>" is printed to the terminal output despite the action reporting as "SUCCESS". The error message should not be visible to the user.

**Example from user observation:**
```
READ - Read JN Recruitment homepage to extract skeleton data (HQ, focus, team size).
SUCCESS
...
READ - Read Tiger Recruitment Agency page to extract skeleton data (HQ, team, focus).
Failed to fetch URL 'https://tiger-recruitment.com/ch/agency/': 404 Client Error: Not Found for url: https://tiger-recruitment.com/ch/agency/
SUCCESS
...
READ - Read Meyer & Associates About page to extract skeleton data (Frankfurt, headcount, specialization).
Failed to fetch URL 'https://www.meyer-associates.de/about': 404 Client Error: Not Found for url: https://www.meyer-associates.de/about
SUCCESS
```

The user states these error messages "should not show".

## Context & Scope

### Regressing Delta
**No regressing delta — this is a cumulative design issue.** The `WebReadAction` inner class in `action_factory.py` was introduced by Case File 16 ("Web scraping errors bubble up to the terminal") to catch the exception from `WebScraperAdapter.get_content()` and return a user-friendly error string. However, that fix also added a `logging.warning()` call (line 65) to aid diagnostics. Separately, the root logger is configured in `__main__.py` with `logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(sys.stderr)], force=True)`. This combination means that the WARNING-level log message propagates to stderr and appears in the user's terminal, interleaved with the normal action output.

### Environmental Triggers
- Any READ action that fetches a URL returning non-200 HTTP status (e.g., 403, 404, 500).
- The message appears via stderr (logging stream handler) and is visible because stderr and stdout are both displayed in the user's terminal.
- The action status is "SUCCESS" because the exception is caught; the error string is returned as the action content. The log message leaks as a side effect.

### Ruled Out
- The `textual_plan_reviewer_previews.py` `app.notify()` call is for TUI notifications, not terminal CLI output — ruled out.
- The `WebScraperAdapter`'s own logging suppression (addressed in Case File 39) is unrelated to this application-level logging.
- The `WebReadAction` catching the exception is correct behavior; the issue is solely with the `logging.warning()` call that was added for diagnostics.

## Diagnostic Analysis

### Causal Model
The faulty system operates as follows:

1. A READ action with a URL resource is dispatched to `ActionFactory._create_read_action()`.
2. `ActionFactory` returns a `WebReadAction` wrapper.
3. `WebReadAction.execute()` calls `self._scraper.get_content(url=kwargs["path"])`.
4. `WebScraperAdapter.get_content()` raises an exception (e.g., HTTP 404).
5. The `except Exception` block in `WebReadAction.execute()` catches it.
6. **Line 65:** `logging.getLogger(__name__).warning("Failed to fetch URL '%s': %s", kwargs.get("path"), e)` — emits a WARNING-level log message.
7. The root logger is configured (in `__main__.py`) with `logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(sys.stderr)], force=True)`.
8. Since WARNING >= INFO, the message is sent to stderr via the `StreamHandler`.
9. The user sees the message "Failed to fetch URL '...': 404 Client Error..." interleaved with their terminal output.
10. **Line 67:** The method returns `f"Error: Failed to fetch URL ({e})"` which becomes the action content. The action executor sees a successful return (no exception), so the action status is "SUCCESS".
11. The user sees "SUCCESS" after the log message, causing confusion: the action succeeded (no crash) but an error message is still visible.

### Discrepancies
- The `logging.warning()` call on line 65 was intended for internal diagnostics but leaks to the user's terminal due to the root logger configuration. (Resolved: identified the exact causal chain.)
- The root logger handler writes to `sys.stderr`, which is typically displayed in the same terminal as stdout, making the message appear interleaved with normal output.

### Investigation History
1. **Grep search (`git grep "Failed to fetch URL"`)** — Located three occurrences: `action_factory.py:65` (logging.warning), `textual_plan_reviewer_previews.py:148` (TUI app.notify), and a test file. Target: `action_factory.py`. (2026-09-03)
2. **Read `action_factory.py` lines 50-80** — Confirmed `WebReadAction.execute()` catches the exception, logs a warning, and returns an error string. The logging.warning() is the source of the terminal-visible message. (2026-09-03)
3. **Read `__main__.py`** — Found `logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(sys.stderr)], force=True)`. This sends all INFO+ messages to stderr. WARNING >= INFO, so the log message passes through. (2026-09-03)
4. **Read previous Case Files 16 and 39** — Confirmed that Case File 16 introduced the try/except+logging fix, and Case File 39 addressed third-party logging pollution but not this application-level logging. (2026-09-03)

## Solution

### Root Cause
The `WebReadAction` inner class in `action_factory.py` (line 65) calls `logging.getLogger(__name__).warning(...)` when a URL fetch fails. The root logger is configured in `__main__.py` with `logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(sys.stderr)])`. Since `WARNING >= INFO`, the log message flows to `stderr` and appears interleaved with normal terminal output, despite the action itself returning a successful status (the exception is caught and a user-friendly error string is returned).

This is the **third iteration** of error handling for this path:
1. **Pre-Case File 16:** Uncaught exceptions propagated to terminal as raw tracebacks.
2. **Case File 16 fix:** Added `try/except` + `logging.warning` to catch exceptions and return a user-friendly error string — but introduced the terminal leak of the log message.
3. **This fix:** Downgrade the log level from `warning` to `debug`, so the diagnostic message is suppressed at the default `INFO` log level.

### Proven Fix
Change the log call in `action_factory.py` line 65 from:
```python
logging.getLogger(__name__).warning("Failed to fetch URL '%s': %s", kwargs.get("path"), e)
```
to:
```python
logging.getLogger(__name__).debug("Failed to fetch URL '%s': %s", kwargs.get("path"), e)
```

**Verification:** The shadow file (`spikes/debug/shadow_action_factory.py`) replicated `WebReadAction` with `logging.debug`. The verification script (`spikes/debug/41-web-scraper-error-no-terminal-shadow-verify.py`) executed against the shadow file and confirmed:
- `Action result: Error: Failed to fetch URL (404 Client Error: Not Found for url: https://www.meyer-associates.de/about)` — the error string is still returned.
- `OK: No log message leaked to stderr` — the stderr capture was empty.
- `SHADOW FIX CONFIRMED: logging.debug is suppressed at INFO level.`

### Preventative Measures
- Use `logging.debug()` for internal diagnostic messages that should never appear in normal user-facing terminal output.
- Keep the root logger at `INFO` level (as it is) so that only warnings and errors intended for the user reach `stderr`.
- The `logging.warning()` call was originally added alongside the Case File 16 fix for internal diagnostics but inadvertently became user-visible. Any future diagnostic logging in action execution paths should default to `debug` unless the message is specifically meant for the user.

### Systemic Audit Results
A `git grep -n "logging.warning" -- src/` found the following occurrences outside of tests:
- **`src/teddy_executor/core/services/action_factory.py:65`** — The call fixed in this case.
- **`src/teddy_executor/core/services/execution_orchestrator.py:118`** — User-facing error about plan execution failure. Intentional, should remain visible.
- **`src/teddy_executor/adapters/outbound/web_scraper_adapter.py`** — Third-party library logging, already suppressed via trafilatura configuration (Case File 39).
- **`src/teddy_executor/adapters/outbound/web_searcher_adapter.py`** — Already uses `logging.debug` in most paths.

No other diagnostic/internal `logging.warning` calls leak to the terminal. No further changes required.
