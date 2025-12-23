# Outbound Adapter: `WebSearcherAdapter`

*   **Status:** Planned

## 1. Description

The `WebSearcherAdapter` is the concrete implementation of the [`IWebSearcher`](../../core/ports/outbound/web_searcher.md) port. It uses the `ddgs` Python library to perform web searches via DuckDuckGo, requiring no API key.

## 2. Implemented Ports

*   [`IWebSearcher`](../../core/ports/outbound/web_searcher.md)

## 3. Implementation Notes

The implementation was de-risked with a technical spike. Key findings are:
*   **Library:** The `ddgs` library (formerly `duckduckgo-search`) is used. It is free and does not require an API key.
*   **Reliability:** This approach is significantly more reliable than attempting to scrape Google directly, which is protected by aggressive anti-bot measures.
*   **Data Mapping:** The `ddgs.text()` function returns a list of dictionaries, where each dictionary contains the keys `title`, `href` (URL), and `body` (snippet). These map directly to the fields required by the `SearchResult` domain object.
*   **Dependency:** This adapter will add the `ddgs` package as a project dependency. The library requires Python `~>=3.10`, which necessitated an update to the project's `pyproject.toml`.

## 4. Key Code Snippet

The core logic, verified in the spike, is as follows:

```python
from ddgs import DDGS

# Inside the adapter's 'search' method
all_query_results = []
queries = ["python design patterns", "hexagonal architecture"]

try:
    with DDGS() as ddgs:
        for query in queries:
            results = list(ddgs.text(query, max_results=10))

            # Here, 'results' would be mapped to a list of
            # SearchResult domain objects.

            # The mapped results would be added to a QueryResult
            # domain object, which is then appended to all_query_results.

    # Finally, a SERPReport is constructed from all_query_results.

except Exception as e:
    # A failure here should be caught and raised as a custom
    # application exception, as per the port contract.
    raise WebSearchError(f"Failed to execute search: {e}")

```

## 5. External Documentation

*   **Library:** [`ddgs` on PyPI](https://pypi.org/project/ddgs/)
