# Slice: 02-02-Web Scraping Resilience

- **Status:** Planned
- **Milestone:** [docs/project/milestones/02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [docs/project/specs/stability-and-bugfixes.md](/docs/project/specs/stability-and-bugfixes.md)
- **Component Docs:** [docs/architecture/adapters/outbound/web_scraper_adapter.md](/docs/architecture/adapters/outbound/web_scraper_adapter.md), [docs/architecture/adapters/outbound/web_searcher_adapter.md](/docs/architecture/adapters/outbound/web_searcher_adapter.md)

## Business Goal
Improve the reliability and depth of information gathered through web scraping and searching to provide better context to AI agents.

## Scenarios
> As an agent, I want to scrape content from a site that blocks generic scrapers so that I can gather the information I need.
```gherkin
Given a URL that returns 403 Forbidden to standard Python-requests User-Agents
When I attempt to scrape the URL using WebScraperAdapter
Then the adapter should rotate its User-Agent and headers
And the content should be successfully extracted
```

> As an agent, I want to read raw content from GitHub so that I can analyze source code or documentation.
```gherkin
Given a GitHub raw URL (e.g., raw.githubusercontent.com)
When I scrape the URL
Then the adapter should return the full raw content of the file
```

> As an agent performing research, I want to see content from the search results so that I don't have to manually READ each link.
```gherkin
Given a set of search queries
When I execute a RESEARCH action
Then the results should contain excerpts or full content from the top results, not just SERP snippets
```

## Edge Cases
- **Persistent 403/404**: If after rotation the site still returns 403/404, report a clear error in the execution report.
- **Large Page Content**: If a scraped page is excessively large, truncate intelligently to avoid context window overflows while providing the most relevant information.
- **Search Result Failures**: If individual links in a search result fail to scrape, provide the snippet as a fallback and log the failure.

## Deliverables
- [x] **Harness** - Create reproduction tests for 403 and GitHub raw issues.
- [x] **Contract** - Update `QueryResult` and `SearchResult` DTOs to include `content`.
- [x] **Logic** - Implement Multi-Stage Stealth Rotation (UA + High-Fidelity Headers) for 403 resilience in `WebScraperAdapter`.
- [x] **Logic** - Implement specialized GitHub Raw extraction in `WebScraperAdapter`.
- [x] **Logic** - Enhance `WebSearcherAdapter` to perform follow-up scraping for top results using the hardened `WebScraperAdapter`.
- [x] **Wiring** - Implement `research.max_results` configuration support, concluding with Sandbox Verification for PNAS 403 bypass, GitHub Raw extraction, and Deepened Research.
- [x] **Logic** - Implement exponential backoff/retry (3 attempts) in `WebScraperAdapter` for 403/5xx errors (Arch 3.3).
- [x] **Refactor** - Make WebScraperAdapter max_retries configurable via IConfigService.
- [ ] **Logic** - Implement intelligent content truncation (configurable limit, default ~5000 chars) for search results in `WebSearcherAdapter` with a hint to `curl` to file for full depth if truncated.
- [ ] **Wiring** - Execute Sandbox Verification to validate exponential backoff behavior and intelligent truncation logic integration.

## Implementation Plan
1. **Targeted Integrity Audit**: Audit current `WebScraperAdapter` and `WebSearcherAdapter`.
2. **Reproduction Spikes**: Verify the failures using the URLs provided in the spec.
3. **Resilience Implementation**: Add headers/UA rotation and GitHub special-casing.
4. **Research Deepening**: Integrate scraper into the searcher workflow.

## Implementation Notes
- **403 Failure (PNAS)**: Diagnostic probing confirmed PNAS returns a 403 with Cloudflare headers when using the default User-Agent. Implemented a fallback in `WebScraperAdapter.get_content` that catches `403 Forbidden` errors and retries using `trafilatura.fetch_url`, which handles stealth headers and rotation internally.
- **GitHub Raw Bug**: Probing revealed that `requests` correctly fetches the raw content, but the `WebScraperAdapter` passes this content to `trafilatura.extract`, which fails to produce output for non-HTML raw files (like README.md). Created `test_get_content_raw_github_returns_content` to assert verbatim content return for `raw.githubusercontent.com` URLs.
- **DTO Refinement**: Refactored `SearchResult` in `src/teddy_executor/core/domain/models/web_search_results.py` to use Python 3.11's `NotRequired` for the `content` field. This ensures `title`, `href`, and `body` are mandatory while explicitly allowing `content` to be omitted. Added comprehensive unit tests in `tests/suites/unit/core/domain/models/test_web_search_results.py`.
- **Green State Management**: Marked reproduction tests in `tests/suites/integration/adapters/outbound/test_web_scraper_resilience.py` as `@pytest.mark.xfail` to maintain a passing test suite during intermediate deliverables until logic is implemented.
- **GitHub Raw extraction**: Refactored `WebScraperAdapter.get_content` to unify the handling of `raw.githubusercontent.com` and `github.com` blob URLs. Both now bypass `trafilatura` and return verbatim text content via `requests.get`, ensuring documentation and source files are not lost to HTML parsing failures.
- **Deep Search Scraping**: Enhanced `WebSearcherAdapter` to accept an optional `IWebScraper` via constructor injection. In the `search` method, if a scraper is present, the adapter iterates through search results and attempts to populate the `content` field for each item. Failures in individual scraping attempts are logged as warnings and caught to ensure the overall search still returns at least the engine's snippet.
- **Wiring**: Integrated `IConfigService` into `WebSearcherAdapter` to support `research.max_results`. Updated `infrastructure.py` and resolved regressions across the integration test suite to ensure consistent dependency injection of the config service and the scraper.
- **Wiring (Sandbox Verification)**: Created `spikes/sandbox/02_02_web_resilience.py` which programmatically verified:
    1. **PNAS 403 Bypass**: Content retrieved after transient retries using UA rotation and trafilatura fallback.
    2. **GitHub Raw Support**: Verbatim extraction from `raw.githubusercontent.com`.
    3. **Deep Search**: Enrichment of DDGS results with full scraped content.
    4. **TUI Boot**: Verified `ReviewerApp` correctly initializes with real container dependencies.
- **Finding (Retry)**: PNAS bypass is transient; requires adapter-level backoff (Arch 3.3).
- **Finding (Truncation)**: Trafilatura cleans HTML noise but preserves full volume. Large results (e.g. Wikipedia) threaten context window stability. Intelligent truncation (capping at ~5000 chars) is required.
- **Exponential Backoff**: Implemented 3-attempt exponential backoff (2^n) in `WebScraperAdapter._fetch_with_rotation` and `_handle_github_raw`. Logic retries on 5xx, 429, and transient connection/timeout errors. Permanent 4xx errors (except 403/406/429) fail-fast without retry.
- **Configurable Retries**: Refactored `WebScraperAdapter` to retrieve `max_retries` from `IConfigService` using the key `research.max_scraper_retries`. Added the key to the default `config.yaml` with a value of 3.
