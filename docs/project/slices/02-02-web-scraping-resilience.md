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
- [ ] **Logic** - Enhance `WebSearcherAdapter` to perform follow-up scraping for top results using the hardened `WebScraperAdapter`.
- [ ] **Wiring** - Implement `research.max_results` configuration support.
- [ ] **Showcase** - Demonstration script validating PNAS (403 bypass), GitHub Raw (README extraction), and Deepened Research (Scraped content in SERP).

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
