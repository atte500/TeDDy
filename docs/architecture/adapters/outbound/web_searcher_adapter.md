# Outbound Adapter: `WebSearcherAdapter`

*   **Status:** Implemented

## 1. Description

The `WebSearcherAdapter` is the concrete implementation of the [`IWebSearcher`](../../core/ports/outbound/web_searcher.md) port. It uses the `ddgs` Python library to perform web searches via DuckDuckGo, requiring no API key.

## 2. Implemented Ports

*   [`IWebSearcher`](../../core/ports/outbound/web_searcher.md)

## 3. Implementation Notes

*   **Library:** The `ddgs` library is used to interact with DuckDuckGo.
*   **Configurability:** Respects `research.max_results` (default 5).
*   **Data Mapping:** Maps `ddgs` output to the `WebSearchResults` contract. The `description` field contains the SERP snippet.
*   **Error Handling:** Individual query failures are logged but do not crash the entire search action, providing partial results to the agent. Persistent library failures are raised as `WebSearchError`.

## 4. External Documentation

*   **Library:** [`ddgs` on PyPI](https://pypi.org/project/ddgs/)
