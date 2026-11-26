# Component Design: WebContentCacheAdapter
- **Status:** Implemented
- **Classification:** Outbound Adapter
- **Source:** [`src/teddy_executor/adapters/outbound/web_content_cache_adapter.py`](/src/teddy_executor/adapters/outbound/web_content_cache_adapter.py)

## Purpose
Implements [`IWebContentCache`](../../core/ports/outbound/web_content_cache.md) on the local filesystem, owning the session cache file's name, shape, atomic write, and merge lock so no core component knows how the cache is persisted.

## Consumers
- [`WebContentService`](../../core/services/web_content_service.md): The only caller.
- [Composition Root](/src/teddy_executor/registries/infrastructure.py): Registers the adapter beside the web scraper whose fetches it stores.

## Dependencies
None — the adapter reads and writes the local filesystem directly and injects no port.

## Class Invariants
- `single_owner_of_format`: The cache filename literal and the flat JSON map shape live here and in this component's tests, nowhere else.
- `atomic_write`: A merge writes a temporary sibling and replaces the cache file, so a crash mid-write never leaves partial JSON behind.
- `locked_merge`: A merge re-reads the on-disk map and writes it back under one process-wide lock, so two concurrent fetches cannot drop each other's entry. The lock is shared across instances because the therefore-stateless adapter is registered transient.
- `tolerant_load`: A missing file, unparseable JSON, a non-mapping document root, and a non-string key or value each read as an empty map.
- `absent_session_noop`: A `None` session root reads as empty and writes nothing, so neither a directory nor a file is created for a session-agnostic export.
- `no_ttl`: Entries never expire; the cache lives for the session and is discarded with it.

## Inbound Ports
None — this is an outbound (driven) adapter.

## Outbound Ports
- **`IWebContentCache`**: The port this adapter implements.

## Data Contracts
- **`.web_cache.json`**: A flat JSON object at `<session_root>/.web_cache.json` mapping URL to its untruncated body, written UTF-8 with no newline translation.
- **`WebContentCacheError`**: Raised when a merge cannot be written, naming the session root. Inherits from `TeddyError`, so the coordinator catches this specific type rather than a bare exception.

## Operations

### `load_entries(session_root: Optional[str]) -> dict[str, str]`
- **Preconditions:** `session_root` is a session directory path, or `None`.
- **Postconditions:** Returns the parsed URL-keyed map. Every tolerated-damage case yields an empty map and raises nothing.
- **Exceptions:** None.

### `merge_entries(session_root: Optional[str], entries: Mapping[str, str]) -> None`
- **Preconditions:** `entries` holds only successfully fetched, untruncated bodies.
- **Postconditions:** The cache directory is created when absent, the existing map is re-read under the merge lock, the supplied entries are layered over it, and the result replaces the file atomically. A `None` root returns without touching the disk.
- **Exceptions:**
  - `WebContentCacheError`: The directory could not be created or the file could not be replaced. The previous cache file is left intact.
