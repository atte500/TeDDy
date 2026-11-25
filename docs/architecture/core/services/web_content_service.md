# Component Design: WebContentService
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/services/web_content_service.py`](/src/teddy_executor/core/services/web_content_service.py)

## Purpose
Owns the single cached-fetch workflow behind every surface that reads a remote resource, so context assembly, a READ on a URL, and the plan reviewer's preview share one cache and one truncation rule instead of three near-copies.

## Consumers
- [`ContextService`](./context_service.md): Resolves a payload's URL scope through the batch operation, verbatim.
- [`ActionFactory`](./action_factory.md): Builds the READ-on-URL wrapper around the single operation, capped.
- [TextualPlanReviewer](../../adapters/inbound/textual_plan_reviewer.md): Serves a URL preview through the single operation.

## Dependencies
- [`IWebScraper`](../ports/outbound/web_scraper.md): Fetches a URL's content. The port returns the verbatim body, so the stored entry is the full text without any flag requesting it.
- [`IWebContentCache`](../ports/outbound/web_content_cache.md): Loads and merges the session map.
- [`IConfigService`](../ports/outbound/config_service.md): Optional handle resolving `read.max_lines`; a `None` handle falls back to the schema default.

## Class Invariants
- `store_verbatim_return_capped`: Every fetch asks the scraper for the untruncated body, merges that body, and caps only the value handed back to a caller who requested a capped read. A stored body is therefore never shorter than what a later payload embeds.
- `announced_cap`: The cap goes through the shared `truncate_lines` helper with `action_type="read"`, so a capped remote read carries the same notice a long local file receives.
- `one_load_per_batch`: The batch operation reads the session map once and reuses it, so a fifty-URL payload costs one parse rather than fifty.
- `successes_only_persisted`: A fetch that raises produces no entry. The batch maps that URL to `None`; the single operation re-raises after merging nothing.
- `one_fetch_per_url_per_batch`: A URL listed twice in a batch is fetched once and both scopes render from the merged result.
- `parallel_misses`: Uncached URLs are fetched concurrently with a bounded worker count, while cached ones are served without touching the scraper.
- `absent_session_uncached`: A `None` session root runs every fetch uncached and creates no file.
- `tolerated_cache_write_failure`: A `WebContentCacheError` raised during a merge is caught as that specific type, logged with the session root, and the freshly fetched body is still returned, because losing a completed fetch to a cache write failure is the worse outcome.

## Inbound Ports
None — this is a core service invoked directly by its three consumers, which own their own inbound ports.

## Outbound Ports
- **`IWebScraper`**, **`IWebContentCache`**: The fetch and store ports this service orchestrates.
- **`IConfigService`**: Optional handle resolving the `read.max_lines` budget for a capped read.

## Data Contracts
- **Batch result:** `dict[str, Optional[str]]` mapping each requested URL to its verbatim body, or `None` when that URL's fetch failed. A `None` value is what a caller renders as missing.
- **Capped result:** `str` — the body truncated at `read.max_lines` through the announced helper when the caller asked for a capped read.

## Operations

### `fetch_one(url: str, *, session_root: Optional[str] = None, truncate: bool = True) -> str`
- **Preconditions:** `url` is a well-formed absolute URL.
- **Postconditions:** Returns the cached body when the session map holds the URL. On a miss it fetches the body untruncated, merges it, and returns it — capped at `read.max_lines` with the announced notice when `truncate` is `True`, verbatim otherwise. Nothing is merged for a URL that failed.
- **Exceptions:**
  - The scraper's own content error propagates unchanged, so each surface keeps its existing translation.
  - `WebContentCacheError` is never propagated; it degrades to the fetched body per `tolerated_cache_write_failure`.

### `fetch_many(urls: Sequence[str], *, session_root: Optional[str] = None) -> dict[str, Optional[str]]`
- **Preconditions:** `urls` holds absolute URLs; duplicates are allowed.
- **Postconditions:** Returns one entry per distinct URL. Cached URLs are served from a single map load, misses are fetched concurrently and untruncated, and every success is merged in one call. A URL whose fetch raised maps to `None`. No body is capped, because assembly embeds cached content verbatim.
- **Exceptions:** None. A per-URL fetch failure is data the caller renders, not an error that aborts the payload.
