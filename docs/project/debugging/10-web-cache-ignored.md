# Bug: Web Cache Ignored Each Turn

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

**Expected:** URLs fetched via the web scraper once per session are cached in `.web_cache.json` and reused on subsequent context assemblies (turns) without re-fetching the remote resource.
**Actual:** Each turn re-fetches all URLs, ignoring the cache. This causes unnecessary network requests, slower context assembly, and potential rate limiting.
**Minimal Reproduction Steps:**
1. Start a TeDDy session with a context file containing a remote URL.
2. Run a turn that uses context assembly.
3. Observe that the URL is fetched (visible in logs/network).
4. Run another turn.
5. Observe the URL is fetched again, despite being already in the cache.

## Context & Scope

### Regressing Delta
Caching was introduced in two commits:
- `4cc546d7 feat(context): add cache_dir parameter to IGetContextUseCase and ContextService`
- `0a51ca91 feat(context): inject web cache check into get_context URL-fetching loop`

The `cache_dir` parameter was added to `IGetContextUseCase.get_context()` and `ContextService.get_context()`. The `SessionOrchestrator.execute()` method correctly passes `cache_dir = str(Path(plan_path).parent.parent)`. However, `PlanningService.generate_plan()` calls `get_context` at line 73 WITHOUT passing `cache_dir`. Since the planner runs each turn in session mode (via `SessionPlanner`), URLs are always re-fetched during planning, defeating the cache entirely.

### Environmental Triggers
None — the bug is deterministic: any caller of `get_context` that omits `cache_dir` will bypass the cache.

### Ruled Out
- `SessionOrchestrator.execute()` at `session_orchestrator.py:240` correctly passes `cache_dir`.
- The cache file I/O logic in `_load_web_cache` and `_save_web_cache` is correct when `cache_dir` is provided.
- `handle_context_gathering` in `session_cli_handlers.py:272` also omits `cache_dir`, but this is a standalone CLI command, not part of the session loop.

## Diagnostic Analysis

### Causal Model
The `ContextService` has a session-level web content cache. When `get_context()` is called with a non-None `cache_dir`, it reads `.web_cache.json` from that directory and serves cached URLs without calling the web scraper. When `get_context()` is called without `cache_dir` (i.e., `None`), `_load_web_cache(None)` returns `{}` unconditionally, meaning every URL is treated as uncached and the web scraper is invoked for every URL, every turn.

The flow per turn is:
1. `SessionPlanner` (or `SessionReplanner`) calls `PlanningService.generate_plan()`
2. `PlanningService.generate_plan()` calls `get_context()` WITHOUT `cache_dir` → URLs fetched fresh, no caching
3. `SessionOrchestrator.execute()` calls `get_context()` WITH `cache_dir` → cache IS used, but this context is used for validation/execution, not for the plan presented to the LLM

The root cause: `PlanningService` does not pass `cache_dir` when gathering context. Since the planner runs on every turn (to generate new plans or respond to validation failures), URLs are always re-fetched during the planning phase.

### Discrepancies
- (none remaining — causal model fully explains the symptom)

### Investigation History
1. Read source files (web_scraper_adapter, context_service, session_service). Discovered the cache logic depends on `cache_dir` parameter being non-None. No bug in cache I/O code itself.
2. Grepped for all callers of `get_context`. Found three call sites:
   - `session_orchestrator.py:240` — passes `cache_dir` correctly.
   - `planning_service.py:73` — call does NOT pass `cache_dir`.
   - `session_cli_handlers.py:272` — does NOT pass `cache_dir` (standalone command).
3. Ran MRE (`spikes/debug/10-web-cache-mre.py`) confirming that `cache_dir=None` causes `_load_web_cache` to return `{}` and the web scraper to be called, while `cache_dir=<valid path>` uses the cache correctly.
4. Verified that the session loop calls `PlanningService.generate_plan()` each turn, which triggers the non-cached code path.

### Systemic Audit
- **Abstract Category:** "Missing parameter in delegation" — a port/interface parameter was added but not all consumers were updated to pass it.
- **Codebase instances:** Two other missed callers: `handle_context_gathering` in `session_cli_handlers.py` (standalone command, low priority) and no other `get_context` callers found. The `CACHE_FILENAME` constant and cache I/O methods are properly encapsulated in `ContextService`.
- **Impact:** Only `PlanningService` affects session flow. The `handle_context_gathering` omission is cosmetic (standalone context command).
- **Preventative measure:** No automated guard exists. The class of bug could be prevented by adding a default-check or parameter validation in `get_context` that warns when `cache_dir` is omitted but URLs are present. However, `cache_dir` is intentionally optional (standalone usage). A broader solution would be a static analysis rule flagging when new parameters are added to interfaces without updating all callers.

## Solution

### Root Cause
`PlanningService.generate_plan()` calls `self._context_service.get_context()` without the `cache_dir` parameter. Since `cache_dir` defaults to `None`, `_load_web_cache(None)` returns an empty dict, causing every URL to be re-fetched via the web scraper on every planning invocation.

### Fix
Added `cache_dir=str(Path(turn_dir).parent)` to the `get_context()` call in `PlanningService.generate_plan()`. The session root directory is `Path(turn_dir).parent`, which is the same directory where `SessionOrchestrator` expects `.web_cache.json` to reside. This ensures the planner and executor share the same cache file.

### Preventative Measures
- **Regression test (`test_bug_10_web_cache`)**: Verifies that `cache_dir` is passed to `get_context()` with the correct value during planning.
- **Systemic audit**: No other session-critical callers were found to be missing `cache_dir`. The only other omission is `handle_context_gathering` (standalone CLI command), which is not part of the session loop and thus low priority.
- **Category awareness**: This bug belongs to the "missing parameter in delegation" class. When adding new optional parameters to core interfaces, all callers should be audited.
