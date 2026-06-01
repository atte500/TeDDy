# Bug: Web Scraper 403 Persistence

- **Status:** Resolved
- **Milestone:** [02-Stability & Polish](/docs/project/milestones/02-stability-and-polish.md)
- **Vertical Slice:** [02-02-Web Scraping Resilience](/docs/project/slices/02-02-web-scraping-resilience.md)

## Symptoms
The `WebScraperAdapter` returns `403 Forbidden` for specific URLs (e.g., PNAS) even though resilience logic (User-Agent rotation/Trafilatura fallback) was supposedly implemented.

## Context & Scope
### Regressing Delta
- `src/teddy_executor/adapters/outbound/web_scraper_adapter.py`: Added 403 fallback to `trafilatura.fetch_url` in turn 02-02.

### Environmental Triggers
- Accessing scientific journals (PNAS, Cambridge, etc.) that employ aggressive bot detection (e.g., Cloudflare).

### Ruled Out
- **GitHub Raw**: Implementation seems correct and verified by tests; focus remains on 403.

## Diagnostic Analysis
### Causal Model
1. `WebScraperAdapter.get_content` initiates a `requests.get` with a hardcoded Chrome User-Agent.
2. High-security sites (PNAS) detect the bot and return a 403 with `Cf-Mitigated: challenge`.
3. The adapter catches the 403 and calls `trafilatura.fetch_url(url)`.
4. `trafilatura.fetch_url` (which uses its own internal fetcher) is *also* blocked by Cloudflare and returns `None`.
5. The adapter sees the falsy result and re-raises the original `HTTPError`. (resolved: confirmed by MRE output).

### Discrepancies
- **Mocked Success vs Live Failure**. The integration tests pass because they mock `trafilatura.fetch_url` to succeed. In reality, `trafilatura` is no more "stealthy" than `requests` against Cloudflare. (resolved: confirmed).
- **Fallback Utility**. Does `trafilatura.fetch_url` provide any value beyond `requests`? (In progress: Researching fetch_url internals).

### Investigation History
1. **Initial Discovery**: User reported 403 errors on a large list of URLs.
2. **Implementation Audit**: Verified `WebScraperAdapter` uses a hardcoded Chrome UA and falls back to `trafilatura.fetch_url` on 403.
3. **MRE Execution**: Executed live spike against PNAS. Observed that resilience tests pass with mocks, but live scraping yields real-world blocking behavior.
4. **Shadow Verification**: Implemented enhanced header rotation in `ShadowWebScraperAdapter`. PNAS network block bypassed (200 OK), but content appears to be a "soft block" or login wall.
5. **Multi-URL Diagnostic**: Executed tests for PNAS, PMC, and Arxiv. Preliminary PNAS results show 403 bypass but "soft block" content. Fixed recursion bug in MRE to complete PMC and Arxiv analysis.
6. **Production Verification**: Applied multi-stage stealth rotation to `WebScraperAdapter`. Verified fix against production code using black-box MRE. Bypassed 403 blocks for all targets; PMC and Arxiv yielded high-quality content.
