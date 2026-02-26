# Outbound Port: `IWebSearcher`

*   **Status:** Implemented

## 1. Description

This port defines the contract for a component that can perform web searches. It abstracts the specific search provider, allowing the core application to request web searches without being coupled to a particular implementation (e.g., DuckDuckGo, Google).

## 2. Interface Definition

### `search(queries: List[str]) -> WebSearchResults`
**Status:** Implemented

*   **Description:** Performs a web search for each query in the provided list.
*   **Parameters:**
    *   `queries` (List[str]): A list of search query strings.
*   **Returns:** A [`WebSearchResults`](../domain/web_search_results.md) `TypedDict` containing the aggregated search results.
*   **Raises:**
    *   [`WebSearchError`](../domain_model.md): If the search operation fails for any reason (e.g., network error, API failure).
