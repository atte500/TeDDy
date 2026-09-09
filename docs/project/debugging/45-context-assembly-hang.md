# Bug: Context assembly hang (pre-request, after turn header)
- **Status:** Unresolved
- **Milestone:** N/A (Ad-hoc regression from recent commits)
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

**Expected behavior:** After the turn header (`[N] session-name | Waiting for agent to respond...`) is displayed, the metadata (model, context tokens, session cost) and the LLM response should appear promptly.

**Actual behavior:** After the "Waiting for..." message, there is a LONG hang before the metadata appears. The user reports this hang is pre-processing (happens before the AI request is sent).

**Platform-dependent behavior:**
- **On Windows:** The hang happens even with NO URLs in context → **universal** pre-request blocking operation.
- **On Mac:** The hang happens with MANY URLs in context → correlates with web cache size.
- The user reports "even with minimal context it takes more than it used to" on Windows.

**Minimal reproduction (Windows):** Start a TeDDy session on Windows with minimal context (no URLs). Observe the delay between "Waiting for..." and metadata appearing.

**Minimal reproduction (Mac/URLs):** Start a TeDDy session on Mac with many URL context entries (e.g., prospect research URLs). Observe the delay growing across turns as the web cache accumulates.

## Context & Scope

### Regressing Delta
There are likely TWO distinct regressions, possibly introduced by different commits:

**Regression A (Windows-specific universal hang):** Root cause UNKNOWN. The "Waiting for..." message is printed at `planning_service.py:39`. The subsequent pre-request pipeline (before the actual LLM call) includes:
1. `_run_preflight_check()` — local validation only (calls `litellm.validate_config(include_remote=False)`).
2. Resolve context paths (file I/O).
3. `fetch_system_prompt()` (file I/O — reads prompt files).
4. `get_text_token_count()` (local tiktoken — confirmed local).
5. `get_context()`:
   - `_load_web_cache()` (reads `.web_cache.json` from disk).
   - For each URL: fetch (or read from cache), then `_save_web_cache()` (writes `.web_cache.json`).
   - `_format_content()` formats all content for the context.
6. `get_context_window()` (pre-emptive hydration — may make HTTP request to OpenRouter API with 10s timeout).
7. `get_token_count()` (local tiktoken — confirmed local).
8. `_perform_generation_with_retry()` — actual LLM call.

The hydration hypothesis (`get_context_window()` making a network call) was ruled out as primary cause because it would affect both Mac and Windows equally — but the user confirms the universal hang is Windows-only.

Possible Windows-specific causes to investigate:
- `litellm.validate_environment()` in `_run_preflight_check()` — heavy imports or system checks slower on Windows.
- `_get_encoding()` first-call tiktoken encoding download (Windows may have different caching behavior).
- File I/O differences (Windows sync I/O vs Mac performance).
- Some subprocess or DLL-loading behavior unique to Windows.

**Regression B (Cross-platform web cache bloat):** Commit `e058e3e9` ("fix(web-scraper): suppress trafilatura logging and cache failed URL fetches") changed the web cache behavior. Before: only successful fetches were cached. After: **failed URL fetches are cached as empty string sentinels** (`web_cache[url] = ""`), and the cache is saved to disk after every URL attempt.

This means:
- Every URL in `turn.context` that fails to fetch (e.g., analytics URLs, protected pages) writes an entry to `.web_cache.json`.
- The cache file grows unboundedly with failed URL entries (no size limit, no TTL, no GC).
- On every context assembly, the **entire cache file is read and written synchronously** (`_load_web_cache` reads all entries, `_save_web_cache` writes atomically with `tmp.write_text(json.dumps(...))`).
- With enough cache entries, this sync I/O becomes a visible delay.

However, the user confirmed: even without URLs, the hang happens on Windows. So the web cache is a contributing factor for URL-heavy sessions but NOT the universal root cause.

### Environmental Triggers
- **Universal hang (Windows):** Any Windows environment. Reproduces regardless of context content.
- **URL-sensitive hang (Mac/Windows):** Sessions with many URLs in `turn.context` or `session.context` (e.g., prospect research, web scraping tasks). Latency increases with cache file size across turns.

### Ruled Out
- **Pre-emptive hydration network call (`get_context_window`)**: Ruled out as primary cause because the hang is Windows-only; a network call to OpenRouter would affect both platforms equally. However, this may compound latency on first turn or when hydrator cache is cold.
- **`time.sleep()` or explicit delays**: Zero hits in pre-request pipeline files.
- **Subprocess spawning in pre-request flow**: Zero hits in `planning_service.py`, `context_service.py`, `session_service.py`.
- **Platform-specific branching**: Zero `platform.system()` / `sys.platform` / `os.name` hits in pre-request pipeline files.
- **Hydrator DI scope as transient**: The `OpenRouterMetadataHydrator` is NOT registered in the DI container (no `IOpenRouterHydrator` registration in `container.py`). It is instantiated directly in the `LiteLLMAdapter` constructor, making its lifecycle tied to the adapter's scope. Since the adapter is registered as transient (like all other services), the hydrator is effectively transient — `_cached_models` is reset per turn. But this is ruled out as primary cause (Windows-only observation).

## Diagnostic Analysis

### Causal Model
**Pre-request pipeline (after "Waiting for..."):**

The flow is: `planning_service.py` prints "Waiting for..." → `_run_preflight_check()` → resolve context → fetch system prompt → `get_text_token_count()` (local) → `get_context()` → build messages → write `input.md` → `get_context_window()` (hydration) → `get_token_count()` (local) → display telemetry → LLM call.

At least one operation in this pipeline has a Windows-specific performance characteristic that causes a blocking delay that is not present on Mac. The most likely candidates (untested) are:
1. `litellm.validate_environment()` in `_run_preflight_check()`.
2. First-call tiktoken encoding download in `_get_encoding()`.
3. File I/O differences in context resolution.
4. An import-heavy initialization in `LiteLLMAdapter` constructor.

### Discrepancies
- The web cache bloat (Regression B) explains URL-heavy hang on Mac but NOT the Windows universal hang. This confirms two separate root causes.
- The hydration hypothesis (`get_context_window()` network call) does NOT align with Windows-only observation. This rules it out as primary universal cause.

### Investigation History
1. **Context assembly timing confirmed**: The hang is pre-processing (user confirmed: "headers get assembled before sending request to ai so it is pre-processing issue not post processing").
2. **Web cache flow mapped**: `get_context()` at `context_service.py:48-85` loads/writes cache on every call. Recent commit `e058e3e9` added failed URL sentinel caching.
3. **Hydration flow mapped**: `planning_service.py:213` calls `get_context_window()` → reads `litellm.model_cost` dict → if model unknown, calls `OpenRouterMetadataHydrator._fetch_models()` which makes HTTP GET to `https://openrouter.ai/api/v1/models` with 10s timeout.
4. **Hydrator DI scope checked**: Not registered in DI container — instantiated directly in `LiteLLMAdapter` constructor, effectively transient. But ruled out as primary cause due to Windows-only observation.
5. **No Windows branches found**: Zero `platform.system()` / `sys.platform` / `os.name` in pre-request pipeline files.
6. **No sleep/timeout found**: Zero `time.sleep()` or retry delays in pre-request pipeline files.
7. **No subprocess in pre-request flow**: Zero `subprocess.run` / `Popen` in `planning_service.py`, `context_service.py`, or `session_service.py`.
8. **get_text_token_count confirmed local**: Uses local tiktoken, not API calls.

## Solution

### Root Cause
**Regression A (Windows-specific universal hang):** Root cause UNKNOWN. The pre-request pipeline between "Waiting for..." and the actual LLM call contains at least one operation with Windows-specific blocking behavior. Candidate operations not yet investigated:
- `litellm.validate_environment()` in `_run_preflight_check()`.
- `LiteLLMAdapter._get_encoding()` first-call tiktoken initialization.
- File I/O in `ContextService.get_context()` file resolution.
- Heavy imports or system calls during adapter initialization.

**Regression B (Cross-platform URL-sensitive hang):** Web cache bloat from failed URL sentinel caching (commit `e058e3e9`). `.web_cache.json` grows unboundedly with empty string entries for failed URLs, and the entire cache is read/written synchronously on every context assembly.

### Proven Fix
TBD by Debugger investigation. For Regression A, profile the pre-request pipeline on Windows to identify the blocking operation. For Regression B, implement cache size limits, TTL, or background/non-blocking cache writes.

### Systemic Prevention
- Add a performance regression test that measures pre-request pipeline latency (from "Waiting for..." to metadata display) on a reference session with known context size.
- Add Windows CI job that runs basic session start/response timing probes.
- Add size limit and TTL to web cache; write cache asynchronously (non-blocking).
- Profile all pre-request operations for platform-dependent performance characteristics.
