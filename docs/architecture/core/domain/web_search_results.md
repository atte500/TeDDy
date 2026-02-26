**Status:** Planned
**Introduced in:** [Slice: Refactor `SERPReport` to `WebSearchResults`](/docs/project/slices/15-refactor-serpreport-to-websearchresults.md)

## 1. Purpose / Responsibility
`WebSearchResults` is a strictly-typed Data Transfer Object (DTO) that represents the complete, aggregated results from one or more web search queries. It serves as the formal data contract for the `IWebSearcher` outbound port.

## 2. Ports
This component is a passive data structure (Value Object / DTO) and does not implement or use any ports. It is the data payload that is passed across the `IWebSearcher` port boundary.

## 3. Implementation Details / Logic
`WebSearchResults` is implemented as a `TypedDict`. This choice provides static type safety and clarity with minimal runtime overhead, aligning with the project's strategy for modernizing legacy data classes. It contains a list of `SearchResult` items, which is also a `TypedDict`.

## 4. Data Contracts / Methods

### `SearchResult` TypedDict
A dictionary representing a single search result item.
-   `title: str`: The title of the search result.
-   `url: str`: The URL of the search result.
-   `snippet: str`: A short description or snippet from the search result page.

### `WebSearchResults` TypedDict
A dictionary representing the full set of results.
-   `results: List[SearchResult]`: A list containing all the individual search result items.
