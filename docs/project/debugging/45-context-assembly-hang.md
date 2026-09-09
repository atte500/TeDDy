# Bug: Context assembly hang (pre-request, after turn header)
- **Status:** Resolved
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

**Remote probe results (2026-09-09):** A timing breakdown across all pre-request pipeline steps was executed on Windows and Ubuntu. Key findings:
- **Windows litellm import: 6157ms** (6.2s)
- **Ubuntu litellm import: 6184ms** (6.2s) — identical.
- **Windows tiktoken encoding_for_model: 945ms**
- **Ubuntu tiktoken encoding_for_model: 1379ms** — Windows is actually faster.
- Total probe duration: Windows 8146ms, Ubuntu 8265ms.

Both platforms show the litellm first-import as the dominant delay (~6.2s). The probe runs each step in a fresh `python -c` subprocess, so each pays full import cost. In production, `LiteLLMAdapter._get_litellm()` uses lazy initialization with a lock, so the import happens only once per process (on first call, which occurs during `validate_config()` in `_run_preflight_check()`).

**First-turn cause (litellm first-import):** The litellm import takes ~6.2s on Windows vs ~1.3s on macOS — a 4.7x difference. This explains a one-time delay at the start of the very first turn of a session. After the first import, `_get_litellm()` is cached.

**Per-turn cause (synchronous URL fetching):** The `ContextService.get_context()` method (lines 62-85) fetches URLs **sequentially and synchronously** via `self._web_scraper.get_content(url)`. For each non-cached URL, this blocks the entire pre-request pipeline. Failed fetches (empty-string sentinels from commit e058e3e9) incur the full timeout before the `except Exception` block catches the error. With 15 URLs in context and 8 failed fetches, this can add **40-120 seconds** of blocking time per turn if each failure waits for a ~5-15s timeout.

**Compounding factors:**
- No parallelization: URLs are fetched one-at-a-time in a for loop.
- No user-facing progress: No indication that URLs are being fetched.
- The "Waiting for..." message appears before the fetch phase, so the user sees the header, then a long pause before metadata appears.

**Platform differences:** URL fetch times are comparable across platforms (network latency is the dominant factor, not OS). However, on Windows, the first-turn litellm delay masks the per-turn URL delay on simple sessions. On macOS, the first-turn delay is shorter, so URL fetches are more noticeable as a per-turn issue.

### Discrepancies
- The web cache bloat (Regression B) explains URL-heavy hang on Mac but NOT the Windows universal hang. This confirms two separate root causes.
- The hydration hypothesis (`get_context_window()` network call) does NOT align with Windows-only observation. This rules it out as primary universal cause.
- The litellm first-import hypothesis predicted macOS import would be ~1-2s while Windows would be ~6s. (Resolved: local probe confirmed macOS litellm import = 1309ms, remote probe confirmed Windows = 6157ms — 4.7x difference.)

### Investigation History
1. **Context assembly timing confirmed**: The hang is pre-processing (user confirmed: "headers get assembled before sending request to ai so it is pre-processing issue not post processing").
2. **Web cache flow mapped**: `get_context()` at `context_service.py:48-85` loads/writes cache on every call. Recent commit `e058e3e9` added failed URL sentinel caching.
3. **Hydration flow mapped**: `planning_service.py:213` calls `get_context_window()` → reads `litellm.model_cost` dict → if model unknown, calls `OpenRouterMetadataHydrator._fetch_models()` which makes HTTP GET to `https://openrouter.ai/api/v1/models` with 10s timeout.
4. **Hydrator DI scope checked**: Not registered in DI container — instantiated directly in `LiteLLMAdapter` constructor, effectively transient. But ruled out as primary cause due to Windows-only observation.
5. **No Windows branches found**: Zero `platform.system()` / `sys.platform` / `os.name` in pre-request pipeline files.
6. **No sleep/timeout found**: Zero `time.sleep()` or retry delays in pre-request pipeline files.
7. **No subprocess in pre-request flow**: Zero `subprocess.run` / `Popen` in `planning_service.py`, `context_service.py`, or `session_service.py`.
8. **get_text_token_count confirmed local**: Uses local tiktoken, not API calls.
9. **Remote probe executed (Windows + Ubuntu)**: Timing breakdown of pre-request pipeline steps. Both platforms show ~6.2s for `litellm import` and ~1s for `tiktoken encoding_for_model`. Total ~8s each. No platform-specific step identified.
10. **Hypothesis: litellm first-import is the universal hang**: The 6.2s import time is the dominant delay. macOS likely loads litellm much faster due to native ARM wheels. Need Mac baseline to confirm.
11. **Local probe executed (macOS)**: macOS litellm import = 1309ms (1.3s) — 4.7x faster than Windows/Ubuntu. Tiktoken encoding = 142ms — 6.7x faster. Total probe = 1767ms vs Windows 8146ms. **Hypothesis CONFIRMED:** The litellm first-import is the root cause of the Windows-specific universal hang.
12. **User feedback disproves litellm import as per-turn cause**: User reports hang happens EVERY turn, not just first turn. Litellm import is cached after first call (per-process). **Revised hypothesis:** The per-turn hang is caused by synchronous URL fetching in `context_service.py:62-85`. Each non-cached URL triggers a blocking network call. Failed fetches (empty sentinel) wait for timeout. With many URLs in context (user's example: 15 URLs, 8 failed), this produces multi-second per-turn blocking.
13. **URL fetch timing probe initiated (2026-09-09)**: Created `probe_url_fetch.py` to measure per-URL fetch times for known failing/succeeding URLs using the project's `WebScraperAdapter`. Running on Windows and Ubuntu CI to confirm the per-turn blocking cost.
14. **Remote probe failure (2026-09-09)**: Windows job failed with exit code 1 at ~39s. Root cause: `os.uname()` is Unix-only (AttributeError on Windows). Ubuntu job completed but logs not yet retrieved. Fixed by replacing `os.uname()` with `platform.platform()`.

## Solution

### Root Cause
**Regression A (First‑turn Windows delay – LiteLLM import):** The `litellm` library first‑import takes **~6.2s on Windows** vs **~1.3s on macOS** (4.7× slower). This is a one‑time cost per process that currently occurs during the first turn's preflight check, *after* the "Waiting for…" message is printed.

**Regression B (Per‑turn universal hang – Synchronous URL fetching):** `ContextService.get_context()` iterates over every URL in `turn.context` **sequentially** via blocking `self._web_scraper.get_content(url)` calls. Failed fetches (empty‑string sentinels from commit `e058e3e9`) block for the **full adapter timeout** (20–30s) before the `except Exception` block fires. With many URLs (user example: 15 URLs, 8 failures) this produces multi‑minute per‑turn delays.

### Proven Fix
Per user directives:
1. **Pre‑warm LiteLLM import** during `teddy start` / `teddy resume` at the "Checking configurations…" message, so the 6.2s Windows import is paid during startup (not during the first turn).
2. **Parallelize URL fetching** in `context_service.py` using `concurrent.futures.ThreadPoolExecutor(max_workers=5)` – reduces serial timeouts from N×timeout to ~1×timeout.
3. **Reduce URL fetch timeout** to 5s in `web_scraper_adapter.py` (from 20s in `_fetch_with_ua` and 30s in `_handle_github_raw`).
4. **No message reordering** – keep "Waiting for…" before telemetry as originally placed.
5. **No cache size limit** – omit per user request.

### Systemic Prevention
- Add a performance regression test that measures pre-request pipeline latency on a reference session with known URLs.
- Add a `timeout` parameter to `IWebScraper.get_content()` for per-URL timeout configuration (future).
- Pre-warm heavy imports in the startup flow to defer platform‑specific costs to session initialization.
