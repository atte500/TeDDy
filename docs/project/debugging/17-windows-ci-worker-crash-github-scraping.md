# Bug: Windows CI Worker Crash in GitHub Scraping Test

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
Expected: `tests/integration/adapters/outbound/test_web_scraper_github_scraping.py` passes on all platforms.
Actual: Worker crashes on Windows CI (`worker 'gw0' crashed`).

## Context & Scope
### Regressing Delta
Unknown, but occurring in `tests/integration/adapters/outbound/test_web_scraper_github_scraping.py`.

### Environmental Triggers
- OS: Windows (CI)
- Runner: `pytest-xdist` (multi-worker)

### Ruled Out
- Ubuntu/macOS CI (assumed passing based on context).

## Diagnostic Analysis
### Investigation History
- [2026-04-17] Verified that `WebScraperAdapter.get_content` imports `trafilatura` even for GitHub URLs, which triggers the load of `lxml` (native extension) and causes worker crashes on Windows CI. Verified via `debug/mre_lazy_load.py` which failed on buggy code.

### Causal Model
The `WebScraperAdapter.get_content` method calls `self._get_trafilatura()` immediately upon entry, which triggers a lazy import of the `trafilatura` library. `trafilatura` depends on `lxml`, a native C extension. On Windows, especially when using `pytest-xdist` for parallel execution, concurrent imports or initializations of native extensions like `lxml` are known to cause intermittent process crashes (segfaults/access violations) if not perfectly isolated.

Even though the crashing test (`test_github_issue_scraping_extracts_description_and_comments`) is for GitHub content and uses BeautifulSoup, the `trafilatura` import happens anyway, making it a likely suspect for the worker crash.

### Discrepancies
- [ ] Worker crashes only on Windows.
- [ ] `WebScraperAdapter` imports a heavy native library (`trafilatura`/`lxml`) even when not needed for the specific URL. (resolved: Verified in code that `_get_trafilatura()` is called at the start of `get_content`)

### Investigation History
- N/A

## Solution
### Implemented Fixes
- Refactored `WebScraperAdapter.get_content` to defer the initialization (and thus the import) of `trafilatura` until it is actually needed for content extraction. This prevents the import of native extensions like `lxml` when scraping GitHub URLs.

### Prevention
- Added a formal regression test `test_web_scraper_github_url_does_not_import_trafilatura` in `tests/suites/integration/core/services/test_lazy_loading_integration.py` which uses a subprocess to verify that `trafilatura` is NOT present in `sys.modules` after a GitHub scrape.
- Performed a systemic audit to ensure no other "heavy" libraries are imported at the module level in `src/`.
