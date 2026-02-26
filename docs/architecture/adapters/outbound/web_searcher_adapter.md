# Outbound Adapter: `WebSearcherAdapter`

*   **Status:** Implemented

## 1. Description

The `WebSearcherAdapter` is the concrete implementation of the [`IWebSearcher`](../../core/ports/outbound/web_searcher.md) port. It uses the `ddgs` Python library to perform web searches via DuckDuckGo, requiring no API key.

## 2. Implemented Ports

*   [`IWebSearcher`](../../core/ports/outbound/web_searcher.md)

## 3. Implementation Notes

*   **Library:** The `ddgs` library is used to interact with DuckDuckGo.
*   **Data Mapping:** The raw results from the `ddgs` library are mapped to the `WebSearchResults` `TypedDict` contract. Specifically, the library's `title`, `href` (as `url`), and `body` (as `snippet`) keys are used to construct the `SearchResult` dictionaries. The adapter aggregates all results into a single `WebSearchResults` object.
*   **Error Handling:** Any exception raised during the interaction with the `ddgs` library is caught and re-raised as a domain-specific `WebSearchError` to honor the port contract.

## 4. External Documentation

*   **Library:** [`ddgs` on PyPI](https://pypi.org/project/ddgs/)
