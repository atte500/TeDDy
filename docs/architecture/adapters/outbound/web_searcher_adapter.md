# Component Design: WebSearcherAdapter
- **Status:** Implemented
- **Source:** [`src/teddy_executor/adapters/outbound/web_searcher_adapter.py`](/src/teddy_executor/adapters/outbound/web_searcher_adapter.py)

## Purpose
Implements the `IWebSearcher` outbound port. It runs DuckDuckGo searches through the `ddgs` library and maps the results to the `WebSearchResults` contract.

## Consumers
- [`ActionFactory`](../../core/services/action_factory.md): Builds `RESEARCH` actions that call the port.

## Dependencies
- [`IConfigService`](../../core/ports/outbound/config_service.md): Reads `research.max_results`.
- **`ddgs`** (external): Supplies the `DDGS` search client; imported lazily inside `search`.
- **`suppressed_logging`** (`teddy_executor.adapters.outbound.suppressed_logging`): Silences the noisy third-party HTTP clients during a search through a counted, thread-safe scope.

## Class Invariants
- `lazy_ddgs_import`: The `ddgs` library loads inside `search`, keeping CLI startup fast.
- `word_boundary_patch`: `_apply_ddgs_monkeypatch` joins extracted fragments with a space, so adjacent words are not concatenated.
- `single_query_fails_loud`: When only one query is supplied, a failure raises `WebSearchError`; a multi-query run records an empty result for the failed query and continues.
- `injectable_client_factory`: The `ddgs_factory` constructor argument defaults to `DDGS`, so tests substitute a fake client.

## Inbound Ports
None — this is an outbound (driven) adapter.

## Outbound Ports
- **`IWebSearcher`**: The driven contract implemented by this adapter. See the [IWebSearcher design](../../core/ports/outbound/web_searcher.md).

## Data Contracts
- **`WebSearchResults`** (`TypedDict`): `query_results: List[QueryResult]`, each carrying `query` and a list of `SearchResult` items (`title`, `href`, `description`).
- **Configuration key:** `research.max_results` (int, default 5) bounds the results per query.

## Operations

### `search(queries) -> WebSearchResults`
- **Preconditions:** `queries` is a non-empty list of query strings.
- **Postconditions:** Returns aggregated results for every query. The `description` field carries the SERP snippet, after a cleanup pass that restores a space after punctuation.
- **Exceptions:** `WebSearchError` when a single-query search fails.

### Internal helpers
`_execute_single_query` runs one query and maps the results, logging a warning and returning an empty list on failure unless it is the only query. `_clean_snippet` repairs missing spaces after punctuation. `_apply_ddgs_monkeypatch` patches the base search engine to preserve word boundaries.
