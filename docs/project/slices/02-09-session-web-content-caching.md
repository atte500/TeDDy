# Slice: 02-09 Session Web Content Caching

- **Status:** To De-risk
- **Type:** Feature
- **Milestone:** [docs/project/milestones/02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [docs/project/specs/stability-and-bugfixes.md](/docs/project/specs/stability-and-bugfixes.md)
- **Component Docs:** [ContextService](docs/architecture/core/services/context_service.md), [SessionOrchestrator](docs/architecture/core/services/session_orchestrator.md)

## Business Goal
Prevent redundant web fetches from URLs in session context files by caching their content within a session. This reduces latency and improves reliability during sequential turns.

## Scenarios

> As a user, I want web content from URLs in `session.context` or `turn.context` to be cached so that subsequent turns do not re-fetch the same URL.
```gherkin
Given a session with a URL in session.context (e.g., "https://example.com/docs")
When the first turn's context is assembled
Then the web content for that URL is fetched and stored in the session cache file
When the second turn's context is assembled
Then the content is retrieved from the cache without a network fetch
```

> As a user, I want cache corruption or missing cache files to be handled gracefully so that the system falls back to fetching fresh content.
```gherkin
Given a session with an existing .web_cache.json file containing invalid JSON
When the context is assembled
Then the system treats the cache as empty and fetches content from the web
```

## Edge Cases

- **Cache Corruption**: If `.web_cache.json` is malformed (invalid JSON), treat as empty cache and log a warning.
- **Network Failure**: If a web fetch fails, do not cache the error – allow re-fetch on subsequent turns.
- **Stateless Mode**: When `get_context` is called without a `cache_dir` (e.g., `PlanningService` for one-shot planning), no caching occurs.
- **Cache Not Pruned**: The cache file persists across the session but is not automatically cleaned on session termination. This is acceptable since the cache is session-local and small.

## Deliverables

- [x] **Contract** – Add `cache_dir: Optional[str] = None` parameter to `ContextService.get_context()` signature.
- [ ] **Contract** – Define cache file format (JSON dict mapping URL -> content) and location (`.teddy/sessions/<name>/.web_cache.json`).
- [ ] **Harness** – Unit tests for caching behavior: cache hit, cache miss, cache corruption, fallback.
- [ ] **Logic** – Implement cache check in `ContextService`: load cache file, check before `_web_scraper.get_content()`, write after successful fetch.
- [ ] **Logic** – Add `_load_web_cache(cache_dir) -> dict` and `_save_web_cache(cache_dir, cache)` private methods.
- [ ] **Wiring** – Update `SessionOrchestrator.execute()` to derive `cache_dir` from session root and pass it to `ContextService.get_context()`.
- [ ] **Refactor** – Update `PlanningService` callers (no change needed – default `cache_dir=None` preserves stateless behavior).

## Implementation Notes

*(To be filled by Developer as implementation proceeds.)*

## Implementation Plan

### Architectural Design
- **Cache Location**: `<session_root>/.web_cache.json` (e.g., `.teddy/sessions/20260124-add-user-auth/.web_cache.json`)
- **Cache Format**: Standard JSON dict: `{"https://url.com": "cached content string"}`
- **Injection Point**: `ContextService.get_context()` accepts optional `cache_dir`. When provided, it loads the cache file on first invocation and checks before calling `IWebScraper`.
- **Lifecycle**: Cache is loaded once per `get_context` call to avoid stale in-memory state. Written after each successful fetch.
- **No TTL**: Caching is intra-session only; a new session starts fresh.

### Data Flow
1. `SessionOrchestrator.execute()` resolves `plan_path` -> `<session_root>/<turn>`
2. Derives `cache_dir = str(Path(session_root).parent)`
3. Calls `context_service.get_context(context_files=scoped_paths, cache_dir=cache_dir)`
4. `ContextService._load_web_cache(cache_dir)` -> cached dict (or empty if missing/corrupt)
5. For each URL, if in cache -> use cached content; else -> fetch via `IWebScraper`, then `_save_web_cache(cache_dir, cache)` with updated entry
6. Cache written atomically (write to temp file, rename) to prevent corruption on crash
