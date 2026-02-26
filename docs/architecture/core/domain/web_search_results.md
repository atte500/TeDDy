**Status:** Implemented
**Introduced in:** [Slice: Refactor `SERPReport` to `WebSearchResults`](/docs/project/slices/15-refactor-serpreport-to-websearchresults.md)

## 1. Purpose / Responsibility
`WebSearchResults` is a strictly-typed Data Transfer Object (DTO) that defines the data contract for the results of one or more web search queries. It replaced the legacy `SERPReport` dataclass to improve type safety and align with modern Python practices using `TypedDict`.

## 2. Ports
This component is a passive data structure (DTO) and does not implement or use any ports. It is the data payload that is passed across the `IWebSearcher` port boundary.

## 3. Implementation Details / Logic
`WebSearchResults` is implemented as a series of nested `TypedDict`s. This choice provides static type safety and clarity with minimal runtime overhead, aligning with the project's strategy for modernizing legacy data classes.

The final as-built structure is:
```python
from typing import List, TypedDict

class SearchResult(TypedDict):
    """Represents a single search result item."""
    title: str
    href: str
    body: str

class QueryResult(TypedDict):
    """Represents the results for a single search query."""
    query: str
    results: List[SearchResult]

class WebSearchResults(TypedDict):
    """Represents the aggregated results from one or more web search queries."""
    query_results: List[QueryResult]
```

## 4. Data Contracts / Methods

### `SearchResult` TypedDict
-   `title: str`: The title of the search result page.
-   `href: str`: The full URL of the search result.
-   `body: str`: A snippet or body text from the search result page.

### `QueryResult` TypedDict
-   `query: str`: The original search query string.
-   `results: List[SearchResult]`: A list of `SearchResult` dictionaries for that query.

### `WebSearchResults` TypedDict
-   `query_results: List[QueryResult]`: A list containing the results for all queries.
