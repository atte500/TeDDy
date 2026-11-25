# Component Design: WebScraperAdapter
- **Status:** Refactoring
- **Source:** [`src/teddy_executor/adapters/outbound/web_scraper_adapter.py`](/src/teddy_executor/adapters/outbound/web_scraper_adapter.py)

## Purpose
Implements the `WebScraper` outbound port. It fetches a URL and converts the response to Markdown, with dedicated paths for PDF text extraction and for GitHub raw content and issue or pull-request conversations.

## Consumers
- [`WebContentService`](../../core/services/web_content_service.md): The only caller. It owns the session cache, the fetch concurrency, and the `read.max_lines` cap, and reaches this adapter for the verbatim extracted body alone.

## Dependencies
- [`IConfigService`](../../core/ports/outbound/config_service.md): Optional; reads `research.max_scraper_retries` to bound every retry loop. The `read.max_lines` cap is not resolved here.
- [`IPdfExtractor`](../../core/ports/outbound/pdf_extractor.md): Optional; turns a fetched PDF payload into text for the PDF branch.
- **`requests`** (external): Performs the HTTP fetch; imported lazily inside each fetch helper.
- **`trafilatura`** (external): Extracts main content to Markdown and supplies a fallback fetcher; imported lazily.
- **`BeautifulSoup`** (external): Parses GitHub HTML for the conversation fallback; imported lazily.
- **`suppressed_logging`** (`teddy_executor.adapters.outbound.suppressed_logging`): Silences third-party logs during a fetch through a counted, thread-safe scope.

## Class Invariants
- `lazy_heavy_imports`: `requests`, `trafilatura`, and `BeautifulSoup` load inside the helper that uses them, keeping CLI startup fast.
- `github_raw_bypass`: A raw or blob GitHub URL is returned verbatim and never passes through `trafilatura.extract`.
- `concurrency_safe_logging`: Log suppression uses a counted scope because `get_content` runs concurrently during context assembly.
- `trafilatura_fallback_after_rotation`: The adapter calls `trafilatura.fetch_url` only after the User-Agent rotation returns no content, so a failed URL is not re-fetched and re-logged.
- `pdf_dispatch_first`: A PDF source is handled before the GitHub and rotation paths, so PDF bytes never reach `trafilatura`.
- `pdf_payload_stays_binary`: The PDF branch fetches raw bytes through its own retrying fetch, because every other fetch helper decodes the response to `str`.
- `verbatim_bodies`: Every branch returns the fetch's full extracted text and never applies a line cap. `read.max_lines` belongs to `WebContentService`, so a stored body is never shorter than what a later payload embeds and the announced-truncation notice is produced by one owner rather than two.

## Inbound Ports
None — this is an outbound (driven) adapter.

## Outbound Ports
- **`WebScraper`**: The driven contract implemented by this adapter. See the [WebScraper design](../../core/ports/outbound/web_scraper.md).

## Data Contracts
- **Configuration keys:** `research.max_scraper_retries` (int, default 3) bounds the retry loop.
- **`get_content` return:** The page content as Markdown text, or the extracted text layer for a PDF source.
- **`PdfExtractionError`** (`TeddyError`): Propagated from `IPdfExtractor` when the fetched PDF cannot be parsed; the adapter names the URL as `source`.

## Operations

### `get_content(url, **_kwargs) -> str`
- **Preconditions:** `url` is a well-formed absolute URL.
- **Postconditions:** Returns the page content as Markdown, untruncated. A PDF URL is fetched as raw bytes and returned as the extracted text layer. A raw or blob GitHub URL returns verbatim text. A GitHub issue or pull-request URL uses the hybrid JSON-then-HTML extractor. Every other URL uses a rotating User-Agent fetch, then falls back to `trafilatura.fetch_url` when the rotation yields no content, and converts the result through `trafilatura.extract`.
- **Exceptions:**
  - `AssertionError`: A PDF URL is fetched while no `IPdfExtractor` was injected, which is a composition-root defect rather than remote input.
  - `PdfExtractionError`: The fetched PDF lacks the `%PDF` magic bytes, cannot be parsed, is encrypted, or carries no text layer.
  - `RequestException`: The PDF byte fetch exhausted its retry budget on a transient failure.

### Internal helpers
`_handle_pdf` asserts the extractor, fetches bytes, and extracts text. `_fetch_pdf_bytes` retries transient failures on the raw byte fetch. `_render_html_content` holds the GitHub-conversation routing and the `trafilatura` markdown conversion. `_handle_github_raw` rewrites blob URLs and fetches raw content. `_fetch_with_rotation` rotates User-Agents with exponential backoff. `_fetch_with_ua` retries transient errors on one User-Agent. `_extract_github_conversation` merges JSON hydration data with CSS-scraped comments. `_parse_github_json` and `_scrape_github_html` implement the two GitHub extraction passes. `_max_scraper_retries` resolves the retry budget shared by every fetcher. `_is_retryable_error` classifies 5xx and 429 as transient.
