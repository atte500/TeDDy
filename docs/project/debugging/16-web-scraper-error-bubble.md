# Bug: Website scraping errors bubble up to the terminal
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
The `WebScraperAdapter` or one of its callers prints raw exception tracebacks to the terminal when a scraping request fails (e.g., network timeout, HTTP 403, invalid domain).  The expected behavior is that such errors are either logged internally, converted to an empty result, or wrapped in a domain‑specific exception — never displayed to the user as a raw Python traceback.

## Context & Scope
### Regressing Delta
**Identified:** `action_factory.py` line 60 calls `self._scraper.get_content(url=kwargs["path"])` WITHOUT a try/except block. When `WebScraperAdapter` raises an HTTP error, it propagates directly to the terminal caller. The commit `8a00c19d` did not change error handling, so this is a pre-existing hole, not a regression.

### Environmental Triggers
Any URL that provokes an HTTP error or network failure triggers the symptom.  The port contract (§WebScraper) permits exceptions to be raised, so the issue could be either in the adapter itself (raising too broadly) or in callers that do not wrap it.

### Ruled Out
(none yet)

## Diagnostic Analysis
### Causal Model
- `WebScraperAdapter.get_content` may raise `requests.exceptions.HTTPError` when HTTP requests fail (or `ConnectionError`, etc.)
- `context_service` wraps `get_content` in `try/except Exception` and sets content to `None` on failure — safe.
- `prompt_manager` does NOT call `get_content` — not involved.
- `action_factory.py` line 60 calls `get_content` WITHOUT any try/except, so when the adapter raises, the exception flies upward to the terminal, producing raw traceback output.
- The bug is not a regression; it's a missing error guard in a single caller.

### Discrepancies
- The port spec says "Raises: Any exception", meaning callers should be prepared. `context_service.py` does catch all exceptions, but `action_factory.py` does not. This explains terminal pollution when the scraper is invoked via an action.
(Resolved: action_factory.py at line 60 calls get_content bare, without catch)
- The MRE should demonstrate the symptom by printing error text on stderr.
(Resolved: confirmed after MRE execution.)

### Investigation History
1. Read `web_scraper_adapter.py` – identified multiple exception‑prone paths (raise of last_error, trafilatura.fetch_url uncaught, _handle_github_raw raise). (2026-08-21)
2. Read `context_service.py` – handles errors via try/except. (2026-08-21)
3. Read `action_factory.py` – line 60 calls get_content bare (no try/except). (2026-08-21)
4. MRE executed (fixed syntax error) – confirmed error appears on stderr. (2026-08-21)
5. Shadow verification: `WebReadAction` with try/except correctly catches error and returns user‑friendly message. (2026-08-21)
6. Shadow fix (WebReadAction try/except) verified via test mock and executed [PASSED]. (2026-08-21)
7. Regression test written and passes against fixed production code [GREEN]. (2026-08-21)

## Solution
### Root Cause
The `WebReadAction` inner class in `action_factory.py` (line 60) called `self._scraper.get_content()` without any error handling. When the `WebScraperAdapter` raises an HTTP error, the exception propagated directly to the terminal as a raw traceback.

### Fix
Wrap the `get_content` call in a try/except block that catches `Exception`, logs a warning, and returns a user‑friendly error string (e.g., `"Error: Failed to fetch URL ({ex})"`).

### Preventative Measures
- **Systemic Pattern:** All callers of outbound ports that can raise exceptions SHOULD have a try/except at the call site to prevent raw exceptions from propagating to the user. This is consistent with the existing pattern in `context_service.py`.
- **Code Review:** When adding new action handlers, ensure any port call that can fail is properly wrapped.
- **Codification:** Add a linter rule or checklist to enforce this pattern.

### Verification
- A shadow file verification confirmed the fix works without touching production code (2026-08-21).
- A regression test will be written in the Implementation phase and must pass against the fixed production code.
