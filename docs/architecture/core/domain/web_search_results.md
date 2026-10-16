# Component Design: WebSearchResults
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/domain/models/web_search_results.py`](/src/teddy_executor/core/domain/models/web_search_results.py)

## Purpose
A strictly-typed Data Transfer Object that defines the data contract for the results of one or more web search queries. It replaced the legacy `SERPReport` dataclass to align with modern `TypedDict` practices.

## Consumers
- [`IWebSearcher`](../ports/outbound/web_searcher.md): Declares `WebSearchResults` as its return type.
- [WebSearcherAdapter](../../adapters/outbound/web_searcher_adapter.md): Populates the nested `TypedDict` structure.

## Dependencies
None — this is a passive data structure.

## Class Invariants
- `nested_typed_dicts`: The structure is composed of nested `TypedDict`s with static keys.

## Inbound Ports
None — this is a passive data structure.

## Outbound Ports
None — this is a passive data structure.

## Data Contracts
- **`SearchResult`** (`TypedDict`): `title: str`, `href: str`, `description: str`.
- **`QueryResult`** (`TypedDict`): `query: str`, `results: List[SearchResult]`.
- **`WebSearchResults`** (`TypedDict`): `query_results: List[QueryResult]`.

## Operations
None — this component holds data only.
