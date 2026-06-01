# Outbound Adapter: `WebSearcherAdapter`

*   **Status:** Implemented

## 1. Description

The `WebSearcherAdapter` is the concrete implementation of the [`IWebSearcher`](../../core/ports/outbound/web_searcher.md) port. It uses the `ddgs` Python library to perform web searches via DuckDuckGo, requiring no API key.

## 2. Implemented Ports

*   [`IWebSearcher`](../../core/ports/outbound/web_searcher.md)

## 3. Implementation Notes

*   **Library:** The `ddgs` library is used to interact with DuckDuckGo.
*   **Configurability:** Respects `research.max_results` (default 5) for the number of SERP items retrieved.
*   **Deep Research (Auto-Scraping):** To reduce agent turns, the adapter performs follow-up scraping for top results:
    - **Depth Control:** Respects `research.auto_scrape_depth` (default 3).
    - **Integration:** Uses the `IWebScraper` port to fetch and extract content for the top N results.
    - **Storage:** Scraped content is stored in the `content` field of the `SearchResult` DTO.
*   **Data Mapping:** Maps `ddgs` output to the `WebSearchResults` contract. The `body` field contains the SERP snippet, while the `content` field contains the results of the auto-scrape.
*   **Error Handling:** Individual query or scraping failures are logged but do not crash the entire search action, providing partial results to the agent. Persistent library failures are raised as `WebSearchError`.

## 4. External Documentation

*   **Library:** [`ddgs` on PyPI](https://pypi.org/project/ddgs/)
