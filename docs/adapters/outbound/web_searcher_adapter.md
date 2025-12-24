# Outbound Adapter: `WebSearcherAdapter`

*   **Status:** Implemented

## 1. Description

The `WebSearcherAdapter` is the concrete implementation of the [`IWebSearcher`](../../core/ports/outbound/web_searcher.md) port. It uses the `ddgs` Python library to perform web searches via DuckDuckGo, requiring no API key.

## 2. Implemented Ports

*   [`IWebSearcher`](../../core/ports/outbound/web_searcher.md)

## 3. Implementation Notes

*   **Library:** The `ddgs` library is used to interact with DuckDuckGo.
*   **Data Mapping:** The results from the library are mapped to the `SearchResult` domain object. Specifically, the library's `href` key is mapped to `url`, and `body` is mapped to `snippet`. The adapter loops through each query and aggregates the results into a single `SERPReport` object.
*   **Error Handling:** Any exception raised during the interaction with the `ddgs` library is caught and re-raised as a domain-specific `WebSearchError` to honor the port contract.

## 4. External Documentation

*   **Library:** [`ddgs` on PyPI](https://pypi.org/project/ddgs/)
