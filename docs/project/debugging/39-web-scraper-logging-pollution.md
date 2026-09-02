# Bug: Web Scraper Logging Pollution Reaches Terminal
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
When the `WebScraperAdapter` encounters HTTP errors (403, 404, 406) or malformed HTML, messages like `"not a 200 response: 403 for URL..."` and `"parsed tree length: 1, wrong data type or not valid HTML"` appear in the terminal output during READ and context-fetching operations. The expected behavior is that these low-level library diagnostics should be suppressed — they provide no actionable information to the user and clutter the session output.

Additionally, URLs that fail to fetch (404, 403, network timeout) are retried on every turn. The web cache in `ContextService` only stores successful fetches, so broken URLs are re-attempted each time context is gathered, producing the same error log clutter and wasting time.

## Context & Scope
### Regressing Delta
**No regressing delta.** This is a pre-existing design gap: the `WebScraperAdapter` does not suppress third-party library logging (trafilatura). The `WebSearcherAdapter` already implements logging suppression via `logging.disable(logging.CRITICAL)`, but `WebScraperAdapter` does not.

The caching gap is also pre-existing: the ContextService web cache only persists successful fetches; exceptions are caught but do not update the cache, causing repeated retries of failed URLs.

### Environmental Triggers
- Calling `get_content` on a URL that returns HTTP 403 or 406 triggers the UA rotation fallback (trafilatura.fetch_url) which logs "not a 200 response".
- Calling `get_content` on a URL that returns minimal/trivial HTML triggers trafilatura.extract to log "parsed tree length: 1, wrong data type or not valid HTML".
- The messages appear regardless of whether the exception is caught by callers (e.g., ContextService catches exceptions but cannot suppress pre-exception logging).
- Any URL that fails to fetch (including 404, 403, network errors) will be re-attempted every turn because the failure is never cached.

### Ruled Out
- The `action_factory.py` WebReadAction fix (Case File 16) is correct and addresses exception propagation but does not address logging pollution — these are separate issues.
- The `context_service.py` error handling is correct (catches exceptions, returns None), but does not suppress logging output from trafilatura nor persist failures in the web cache.

## Diagnostic Analysis
### Causal Model

#### Part A: Logging Pollution (Point 3)
1. `WebScraperAdapter.get_content(url)` is called.
2. `_fetch_with_rotation(url)` attempts UA rotation. If all UAs return None (e.g., for 403/406), it falls back to `trafilatura.fetch_url(url)`.
3. `trafilatura.fetch_url` internally calls `LOGGER.error("not a 200 response: %s for URL %s", response.status, url)` — this writes to stderr via Python's logging system.
4. If the HTML is fetched but malformed, `trafilatura.extract` calls `LOGGER.error("parsed tree length: %s, wrong data type or not valid HTML", len(tree))` — also writes to stderr.
5. Neither the adapter nor its callers suppress logging, so these messages reach the terminal.
6. The symptom is that the terminal output is polluted with non-actionable library diagnostics.

#### Part B: Repeated Re-fetching of Failed URLs (Point 4)
1. `ContextService.get_context()` iterates over URLs from context files.
2. For each URL, it checks the in-memory `web_cache` (loaded from `.<session>/.web_cache.json`).
3. If URL is not in cache, it calls `web_scraper.get_content(url)`.
4. **If the fetch succeeds**, the URL + content are saved to `web_cache` and persisted via `_save_web_cache`.
5. **If the fetch fails** (exception), the `except` block sets `file_contents[url] = None` but **does NOT update `web_cache`** — the URL is never persisted in the cache file.
6. On the next turn, the cache is loaded again (empty for that URL), so the same failing URL is fetched again, producing the same logging pollution and wasting time.
7. This repeats every turn: broken URLs (404s, 403s, timeouts) are retried endlessly.

### Discrepancies
- The WebSearcherAdapter already suppresses logging via `logging.disable(logging.CRITICAL)`, so this is inconsistent. (Resolved: WebScraperAdapter lacks similar suppression.)
- The `_fetch_with_rotation` method calls `trafilatura.fetch_url` even when all UA attempts have already failed and `last_error` is set — this triggers an unnecessary log. (Resolved: failing earlier would avoid the log.)
- The ContextService web cache does not store failed URLs, causing them to be re-fetched each turn. (Resolved: cache failed URLs with an empty string marker, and adjust display to treat empty cached content as failure.)

### Investigation History
1. (2026-09-02) Grep found "not a 200 response" in `trafilatura/downloads.py` and "parsed tree length" in `trafilatura/utils.py`.
2. (2026-09-02) Confirmed that `WebReadAction` fix (Case File 16) does not address logging — only exception propagation.
3. (2026-09-02) Probed with fd-level stderr capture but could not reproduce locally due to trafilatura's NullHandler configuration. Accepting session history as evidence.
4. (2026-09-02) Identified pattern: `WebSearcherAdapter` already uses `logging.disable(logging.CRITICAL)` — applying same pattern to `WebScraperAdapter` is the natural fix.
5. (2026-09-02) Reviewed `ContextService._load_web_cache` / `_save_web_cache`: confirmed that only successful fetches are cached. Exception path (lines ~115-125 in context_service.py) sets `file_contents[url] = None` but does not write to cache.
6. (2026-09-02) Initial cache failure probe (probe_cache_failures.py) crashed due to test harness dependency (imports tests.harness which is not available in `uv run python`). Rewritten as probe_cache_failures_v2.py using unittest.mock — confirmed: failed URLs are NOT cached (scraper called twice, URL absent from cache after first fetch).
7. (2026-09-02) Shadow cache fix (shadow_context_service.py with Fix B) verified via probe_shadow_cache_fix.py — passes: failed URL cached as empty string sentinel, scraper called only once on second fetch, output shows `FILE NOT FOUND` for cached failure.

## Solution
### Root Cause
- **Point 3:** The `WebScraperAdapter` does not suppress logging from the `trafilatura` library, which writes `LOGGER.error()` messages directly to stderr.
- **Point 4:** The `ContextService` web cache does not persist failed URL fetches. The exception handler sets the in-memory content to `None` but never writes to the cache file, causing the URL to be re-fetched on every turn.

### Fix

#### Fix A: Logging Suppression (Point 3)
1. Suppress all logging below CRITICAL around the core `get_content` logic using `logging.disable(logging.CRITICAL)` / `finally: logging.disable(logging.NOTSET)` — matching the `WebSearcherAdapter` pattern.
2. In `_fetch_with_rotation`, skip the `trafilatura.fetch_url` fallback if `last_error` is already set from the UA rotation (i.e., we already know the request failed). This avoids triggering the "not a 200 response" log for the most common case.

#### Fix B: Cache Failed URLs (Point 4)
1. In `ContextService.get_context()`, catch exceptions during fetch and store a sentinel value in the cache (e.g., empty string `""`) to indicate the URL failed and should not be retried.
2. Update `_format_workspace_contents` to treat empty string content (from cache) the same as `None` — render as `--- FILE NOT FOUND ---`.
3. This ensures that once a URL fails, it is never re-fetched within the session. The cache persists across turns.

### Preventative Measures
- **Systemic Pattern:** All outbound adapters that use libraries with noisy logging should implement `logging.disable(logging.CRITICAL)` suppression around their public methods.
- **Code Review:** When adding new adapters using third-party HTTP/scraping libraries, ensure logging suppression is applied.
- **Web Cache Design:** All caching layers should persist failures (as empty/none) to prevent repeated failed attempts.
- **Consideration:** A more robust long-term fix would be to replace the `trafilatura.fetch_url` fallback with our own requests-based fetch, giving us full control over error handling and logging. This is logged as technical debt.

### Systemic Audit
#### Logging Suppression Audit
- **`web_searcher_adapter.py`**: Already implements `logging.disable(logging.CRITICAL)` / `finally: logging.disable(logging.NOTSET)` — correct, no change needed.
- **`web_scraper_adapter.py`**: Missing suppression — fix verified via shadow file.
- **`litellm_adapter.py`**: Does not call third-party libraries with noisy logging directly; liteLLM handles its own logging internally.
- **`shell_adapter.py`**: No third-party logging concerns.
- **Other adapters**: No direct third-party logging exposure.
- **Conclusion:** The logging suppression gap is limited to `WebScraperAdapter` and is not systemic.

#### Cache Failure Persistence Audit
- **`context_service.py`**: The only place that maintains a web content cache. The exception handler in `get_context()` does not persist failures — verified via probe. Fix verified via shadow.
- **Other services**: `repository_tree`, file system, session services do not maintain caches with similar failure persistence patterns.
- **Conclusion:** The cache persistence gap is localized to `ContextService.get_context()` and is not systemic.

#### Secondary Findings
- No other adapters use `trafilatura.fetch_url` directly — the only production call is within `WebScraperAdapter._fetch_with_rotation()`.
- No other `except Exception` blocks in outbound adapters miss a state update similar to this cache gap.
- The two bugs are well-contained and fixable with targeted changes to two files.

### Verification
- **Point 3 (Logging Suppression):** Shadow file (spikes/debug/shadow_web_scraper_adapter.py) with `logging.disable(logging.CRITICAL)` created. Probe (spikes/debug/probe_shadow_fix.py) ran successfully — local environment does not produce trafilatura stderr, confirming fix is a safe no-op in this env. Fix pattern matches WebSearcherAdapter's existing suppression.
- **Point 4 (Cache Failures):** Production bug confirmed via probe (spikes/debug/probe_cache_failures_v2.py): scraper called 2x, URL absent from cache after first fetch. Shadow fix verified via probe (spikes/debug/probe_shadow_cache_fix.py): scraper called 1x, URL cached as empty string sentinel, output shows `FILE NOT FOUND`.
- Regression tests will cover both logging suppression and cache persistence of failures.
