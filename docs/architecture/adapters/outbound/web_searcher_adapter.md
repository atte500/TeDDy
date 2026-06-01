# Outbound Adapter: `WebSearcherAdapter`

*   **Status:** Implemented

## 1. Description

The `WebSearcherAdapter` is the concrete implementation of the [`IWebSearcher`](../../core/ports/outbound/web_searcher.md) port. It uses the `ddgs` Python library to perform web searches via DuckDuckGo, requiring no API key.

## 2. Implemented Ports

*   [`IWebSearcher`](../../core/ports/outbound/web_searcher.md)

## 3. Implementation Notes

*   **Library:** The `ddgs` library is used to interact with DuckDuckGo.
*   **Configurability:** Respects `research.max_results` (default 5) and `research.max_content_length` (default 5000).
*   **Intelligent Truncation:** Scraped content is capped at `research.max_content_length` to protect the context window. A hint is appended to the content when truncation occurs. The logic is defensive against non-integer config values (e.g., from mocks) and falls back to 5000.
*   **Deep Research (Auto-Scraping):** To reduce agent turns, the adapter performs follow-up scraping for retrieved search results if an `IWebScraper` is provided:
    - **Integration:** Uses a constructor-injected `IWebScraper` port to fetch and extract content for every result.
    - **Storage:** Scraped content is stored in the `content` field of the `SearchResult` DTO.
    - **Fault Tolerance:** If scraping fails for an individual page (e.g., timeout, 403, network error), the adapter MUST catch the exception, log the failure, and return the result with the `body` (snippet) only. A failure on one page MUST NOT invalidate other results or fail the entire `RESEARCH` action.
*   **Data Mapping:** Maps `ddgs` output to the `WebSearchResults` contract. The `body` field contains the SERP snippet, while the `content` field contains the results of the auto-scrape.
*   **Error Handling:** Individual query or scraping failures are logged but do not crash the entire search action, providing partial results to the agent. Persistent library failures are raised as `WebSearchError`.

## 4. External Documentation

*   **Library:** [`ddgs` on PyPI](https://pypi.org/project/ddgs/)
