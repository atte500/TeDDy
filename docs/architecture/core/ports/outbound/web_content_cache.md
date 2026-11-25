# Component Design: WebContentCache
- **Status:** Planned
- **Source:** [`src/teddy_executor/core/ports/outbound/web_content_cache.py`](/src/teddy_executor/core/ports/outbound/web_content_cache.py)

## Purpose
Defines the outbound port for the session-scoped store of fetched remote content, so the one cache behind every fetch surface is a contract rather than a private detail of a core service.

## Consumers
- [`WebContentService`](../../services/web_content_service.md): Loads the session map once per assembly and merges the body of every successful fetch.

## Dependencies
None — this port declares no injected dependencies.

## Class Invariants
- `url_keyed`: An entry is keyed by its absolute URL alone, so the same URL in two scopes costs one fetch and renders in both.
- `untruncated_bodies`: A stored body is the fetch's full text, never a capped preview, because context assembly embeds cached content verbatim.
- `absence_means_failure`: Only successful fetches are stored. A failed fetch leaves no entry, so a later turn retries instead of replaying a negative marker for the rest of the session.
- `empty_body_is_a_fact`: An empty string is a stored body produced by a successful response with no extractable text, and is distinct from an absent entry.
- `absent_session_disables_cache`: A `None` session root reads as an empty map and accepts no merge, so a session-agnostic export neither reads nor creates cache state.
- `tolerant_load`: A missing, unparseable, or non-string-valued file reads as an empty map, because cache damage must never block a turn.
- `runtime_checkable`: The protocol supports `isinstance` checks.

## Inbound Ports
None — this is an outbound (driven) port.

## Outbound Ports
- **`WebContentCache`**: The driven contract consumed by `WebContentService` and implemented by the `WebContentCacheAdapter`.

## Data Contracts
- **Cache map:** `dict[str, str]` mapping an absolute URL to the untruncated extracted body for one session.
- **`WebContentCacheError`** (`teddy_executor.core.domain.models.exceptions`): Raised when a merge cannot be persisted, carrying the session root that failed. Inherits from `TeddyError` so the coordinator can catch this specific failure and keep the fetched body.

## Operations

### `load_entries(session_root: Optional[str]) -> dict[str, str]`
- **Preconditions:** `session_root` is a session directory path, or `None` when no session is in scope.
- **Postconditions:** Returns every URL-keyed body stored for that session. A `None` root, an absent file, an unparseable file, and a map holding a non-string key or value each yield an empty map.
- **Exceptions:** None. A damaged cache degrades to empty so the fetch proceeds rather than blocking the turn.

### `merge_entries(session_root: Optional[str], entries: Mapping[str, str]) -> None`
- **Preconditions:** `entries` carries only successfully fetched bodies, every value untruncated.
- **Postconditions:** Each supplied URL is written into the session map, entries it does not name survive, and the file is replaced atomically. A `None` root writes nothing.
- **Exceptions:**
  - `WebContentCacheError`: The merge could not be persisted. The on-disk map is left as it was rather than partially written.
