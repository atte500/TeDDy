# Component Design: WebScraperAdapter
- **Status:** Implemented
- **Source:** [`src/teddy_executor/adapters/outbound/web_scraper_adapter.py`](/src/teddy_executor/adapters/outbound/web_scraper_adapter.py)

## Purpose
Implements the `WebScraper` outbound port. It fetches a URL and converts the response to Markdown, with a dedicated path for GitHub raw content and issue or pull-request conversations.

## Consumers
- [`ActionFactory`](../../core/services/action_factory.md): Builds remote `READ` actions that call the port.
- [`ContextService`](../../core/services/context_service.md): Fetches context URLs concurrently through a thread pool.

## Dependencies
- [`IConfigService`](../../core/ports/outbound/config_service.md): Optional; reads `research.max_scraper_retries` and `read.max_lines`.
- **`requests`** (external): Performs the HTTP fetch; imported lazily inside each fetch helper.
- **`trafilatura`** (external): Extracts main content to Markdown and supplies a fallback fetcher; imported lazily.
- **`BeautifulSoup`** (external): Parses GitHub HTML for the conversation fallback; imported lazily.
- **`suppressed_logging`** (`teddy_executor.adapters.outbound.suppressed_logging`): Silences third-party logs during a fetch through a counted, thread-safe scope.

## Class Invariants
- `lazy_heavy_imports`: `requests`, `trafilatura`, and `BeautifulSoup` load inside the helper that uses them, keeping CLI startup fast.
- `github_raw_bypass`: A raw or blob GitHub URL is returned verbatim and never passes through `trafilatura.extract`.
- `concurrency_safe_logging`: Log suppression uses a counted scope because `get_content` runs concurrently during context assembly.
- `trafilatura_fallback_after_rotation`: The adapter calls `trafilatura.fetch_url` only after the User-Agent rotation returns no content, so a failed URL is not re-fetched and re-logged.

## Inbound Ports
None — this is an outbound (driven) adapter.

## Outbound Ports
- **`WebScraper`**: The driven contract implemented by this adapter. See the [WebScraper design](../../core/ports/outbound/web_scraper.md).

## Data Contracts
- **Configuration keys:** `research.max_scraper_retries` (int, default 3) bounds the retry loop; `read.max_lines` (int) caps truncated output.
- **`get_content` return:** The page content as Markdown text.

## Operations

### `get_content(url, truncate=True, **_kwargs) -> str`
- **Preconditions:** `url` is a well-formed absolute URL.
- **Postconditions:** Returns the page content as Markdown. A raw or blob GitHub URL returns verbatim text. A GitHub issue or pull-request URL uses the hybrid JSON-then-HTML extractor. Every other URL uses a rotating User-Agent fetch, then falls back to `trafilatura.fetch_url` when the rotation yields no content, and converts the result through `trafilatura.extract`. When `truncate` is `True`, the output is capped at `read.max_lines`.

### Internal helpers
`_handle_github_raw` rewrites blob URLs and fetches raw content. `_fetch_with_rotation` rotates User-Agents with exponential backoff. `_fetch_with_ua` retries transient errors on one User-Agent. `_extract_github_conversation` merges JSON hydration data with CSS-scraped comments. `_parse_github_json` and `_scrape_github_html` implement the two GitHub extraction passes. `_truncate_content` applies the line cap. `_is_retryable_error` classifies 5xx and 429 as transient.
