# Slice: 02-09 Session Web Content Caching

- **Status:** Planned
- **Type:** Feature
- **Milestone:** [docs/project/milestones/02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [docs/project/specs/stability-and-bugfixes.md](/docs/project/specs/stability-and-bugfixes.md)
- **Prototype:** [spikes/prototypes/02-09-web-content-caching.py](/spikes/prototypes/02-09-web-content-caching.py)
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

- [ ] **Contract** – Add `cache_dir: Optional[str] = None` parameter to `IGetContextUseCase.get_context()` Protocol and `ContextService.get_context()` implementation.
- [ ] **Harness** – Unit tests for `_load_web_cache` corruption handling, `_save_web_cache` atomic write, cache hit/miss in `get_context` URL loop.
- [ ] **Logic** – Add `_load_web_cache(cache_dir) -> dict` and `_save_web_cache(cache_dir, cache)` private methods to `ContextService`.
- [ ] **Logic** – Inject cache check into `get_context` URL-fetching loop: load cache once, check before each `IWebScraper.get_content()` call, save after each successful fetch. Do NOT cache failures.
- [ ] **Wiring** – Update `SessionOrchestrator.execute()` to derive `cache_dir = str(Path(plan_path).parent.parent)` and pass it to `ContextService.get_context()`.
- [ ] **Refactor** – No code changes needed for `PlanningService` or `session_cli_handlers` (default `cache_dir=None` preserves stateless behavior).
- [ ] **Documentation** – Update `ContextService` component doc with cache lifecycle details.
- [ ] **Documentation** – Update `SessionOrchestrator` component doc with cache_dir derivation.

## Implementation Notes

### Prototype Findings (Validated)
- **Cache file location:** `<session_root>/.web_cache.json` — confirmed via `Path(plan_path).parent.parent` derivation.
- **Slice doc correction:** The Implementation Plan draft incorrectly specified `cache_dir = str(Path(session_root).parent)`. The correct derivation is `cache_dir = str(Path(plan_path).parent.parent)` (which equals `str(session_root)`).
- **Atomic write pattern:** Write to `.web_cache.json.tmp`, then `Path.replace()` to `.web_cache.json`. No `IFileSystemManager` changes needed.
- **`_ensure_loaded()` timing:** The cache must be loaded (or attempted) BEFORE each write operation to detect corruption. If the file is corrupt, it's treated as empty and overwritten.
- **Backward compatibility confirmed:** When `cache_dir=None` (existing callers `PlanningService`, `session_cli_handlers`), no caching occurs. All 3 existing callers remain unchanged.
- **Network failures NOT cached:** If `IWebScraper.get_content()` raises, the error is stored as `None` in the result but NOT added to the cache. Subsequent calls retry the fetch.
- **No contract changes to outbound ports:** Cache logic lives entirely inside `ContextService` as private methods. No new methods on `IFileSystemManager` or `IWebScraper` are required.
- **Prototype verified:** All 7 scenarios (cache hit, miss->hit, corruption, backward compat, network failure, path derivation, full integration) pass validation. The prototype is linked in slice metadata.

## Implementation Plan

### Architectural Design
- **Cache Location**: `<session_root>/.web_cache.json` (e.g., `.teddy/sessions/20260124-add-user-auth/.web_cache.json`)
- **Cache Format**: Standard JSON dict: `{"https://url.com": "cached content string"}`
- **Injection Point**: `ContextService.get_context()` accepts optional `cache_dir`. When provided, it loads the cache file before the URL-fetching loop in `_format_workspace_contents()` and checks before calling `IWebScraper.get_content()`.
- **Lifecycle**: Cache is loaded fresh each `get_context` call to reflect any disk-side changes. Written atomically after each successful fetch.
- **No TTL**: Caching is intra-session only; a new session starts fresh.
- **No Contract Changes**: The cache implementation lives entirely inside `ContextService` as private methods (`_load_web_cache`, `_save_web_cache`). Python's `Path.replace()` provides atomic rename without requiring `IFileSystemManager` changes.
- **Cache Store Logic**: `_ensure_loaded()` must be called BEFORE each write operation to detect corruption on the first write attempt. If the cache file is corrupt, it's treated as empty and overwritten.

### Data Flow (Validated by Prototype)
1. `SessionOrchestrator.execute()` resolves `plan_path` (e.g., `.../sessions/mysession/01/plan.md`)
2. Derives `cache_dir = str(Path(plan_path).parent.parent)` — i.e., `.../sessions/mysession` (the session root directory)
   - **Note:** The initial draft incorrectly used `str(Path(session_root).parent)`. The correct expression is `str(Path(plan_path).parent.parent)` which equals `str(session_root)`.
3. Calls `context_service.get_context(context_files=scoped_paths, agent_name=agent_name, cache_dir=cache_dir)`
4. `ContextService._load_web_cache(cache_dir)` loads `.web_cache.json` from disk (or returns `{}` if missing/corrupt)
5. For each URL in the resolved content paths:
   - Check if URL exists in loaded cache dict -> use cached content
   - Otherwise: fetch via `IWebScraper.get_content(url)`, then `_save_web_cache(cache_dir, cache)` with updated entry.
6. Cache written atomically (write to temp file `.web_cache.json.tmp`, then `Path.replace()` to `.web_cache.json`) to prevent corruption on crash.

### Delta Analysis (Changes Required)

#### `ContextService` (`src/teddy_executor/core/services/context_service.py`)

1. **Add `cache_dir` parameter to `get_context()`:**
   ```python
   def get_context(
       self,
       context_files: Optional[Dict[str, Sequence[str]]] = None,
       include_tokens: bool = True,
       agent_name: str = "Unknown",
       total_window: int = 0,
       cache_dir: Optional[str] = None,  # NEW
   ) -> ProjectContext:
   ```

2. **Add private cache methods:**
   ```python
   def _load_web_cache(self, cache_dir: Optional[str]) -> Dict[str, str]:
       """Load cache from disk, returning {} on corruption/missing."""
       if not cache_dir:
           return {}
       cache_path = Path(cache_dir) / CACHE_FILENAME
       if not cache_path.exists():
           return {}
       try:
           raw = cache_path.read_text(encoding="utf-8")
           parsed = json.loads(raw)
           if isinstance(parsed, dict) and all(isinstance(v, str) for v in parsed.values()):
               return parsed
       except (json.JSONDecodeError, OSError):
           pass
       return {}

   def _save_web_cache(self, cache_dir: str, cache: Dict[str, str]) -> None:
       """Write cache atomically: temp file -> Path.replace()."""
       cache_dir_path = Path(cache_dir)
       cache_dir_path.mkdir(parents=True, exist_ok=True)
       target = cache_dir_path / CACHE_FILENAME
       tmp = cache_dir_path / f"{CACHE_FILENAME}.tmp"
       tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
       tmp.replace(target)
   ```

3. **Modify URL-fetching loop in `get_context()`:**
   ```python
   web_cache = self._load_web_cache(cache_dir)
   for url in urls:
       if url in web_cache:
           file_contents[url] = web_cache[url]
       else:
           try:
               content = self._web_scraper.get_content(url)
               file_contents[url] = content
               web_cache[url] = content
               if cache_dir:
                   self._save_web_cache(cache_dir, web_cache)
           except Exception:
               file_contents[url] = None
   ```

#### `SessionOrchestrator` (`src/teddy_executor/core/services/session_orchestrator.py`)

1. **In `execute()` method**, derive `cache_dir` before calling `get_context()`:
   ```python
   cache_dir: Optional[str] = None
   if is_session and plan_path:
       cache_dir = str(Path(plan_path).parent.parent)

   project_context = self._context_service.get_context(
       context_files=context_files,
       agent_name=agent_name,
       total_window=total_window,
       cache_dir=cache_dir,
   )
   ```

#### `IGetContextUseCase` (`src/teddy_executor/core/ports/inbound/get_context_use_case.py`)

1. **Add `cache_dir` parameter to the Protocol:**
   ```python
   def get_context(
       self,
       context_files: Optional[Dict[str, Sequence[str]]] = None,
       include_tokens: bool = True,
       agent_name: str = "Unknown",
       total_window: int = 0,
       cache_dir: Optional[str] = None,  # NEW
   ) -> ProjectContext:
   ```

#### `PlanningService` & `session_cli_handlers`

1. **No code changes required.** Default `cache_dir=None` preserves stateless behavior.
