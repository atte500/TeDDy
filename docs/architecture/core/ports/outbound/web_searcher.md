# Component Design: IWebSearcher
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/ports/outbound/web_searcher.py`](/src/teddy_executor/core/ports/outbound/web_searcher.py)

## Purpose
Defines the outbound port for running web searches and returning structured results. It abstracts the search provider from the core.

## Consumers
- [`ActionFactory`](../../services/action_factory.md): Builds `RESEARCH` actions that call the port.

## Dependencies
- **`WebSearchResults`** (`teddy_executor.core.domain.models.web_search_results`): The return type.

## Class Invariants
- `abstract_base_class`: The port is an `ABC`; implementations override `search`.

## Inbound Ports
None — this is an outbound (driven) port.

## Outbound Ports
- **`IWebSearcher`**: The driven contract consumed by the action layer and implemented by the `WebSearcherAdapter`.

## Data Contracts
- **`WebSearchResults`** (`TypedDict`): `query_results: List[QueryResult]`, each carrying `query` and a list of `SearchResult` items (`title`, `href`, `description`).

## Operations

### `search(queries) -> WebSearchResults`
- **Preconditions:** `queries` is a non-empty list of query strings.
- **Postconditions:** Returns aggregated results for every query.
- **Exceptions:** Raises a web-search error when the search fails.
