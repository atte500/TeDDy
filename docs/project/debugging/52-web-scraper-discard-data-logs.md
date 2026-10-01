# Bug: Web scraper "discarding data" logs pollute session console output

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

During an interactive TeDDy session, unmanaged log lines of the form `discarding data: <URL>` are printed to the console, interleaved with TeDDy's own output. They are not part of any plan, report, or agent message.

Console excerpt (user report):

```
[05] way-schedule-send-directly-instead | Waiting for pathfinder to respond...
discarding data: https://documenter.getpostman.com/view/6493518/2s9YR3dFfb
discarding data: https://api.warmupinbox.com/api-doc
• Model: deepseek/deepseek-v4-flash
• Context: 32.1k / 1000.0k tokens
• Session Cost: $0.0074
```

- **Expected:** Console output during a session contains only TeDDy-managed messages (turn banners, action logs, reports, session metadata).
- **Actual:** Raw-URL log lines appear mid-session, apparently around a turn that performed web research/reading (URLs point to API documentation portals with little extractable content, e.g., Postman documenter pages).

Minimal reproduction steps:
1. Run an interactive session where the agent performs web research/reading that fetches pages yielding empty or discarded extraction results.
2. Observe `discarding data: <URL>` lines printed directly to the console.

## Context & Scope

### Regressing Delta
Not a code regression. The emitter is third-party: `.venv/lib/python3.13/site-packages/trafilatura/core.py:320` — `LOGGER.warning("discarding data: %s", options.source)` inside `bare_extraction()`'s `except (TypeError, ValueError)` block. The observed lines contain real URLs (not "None"), proving Case File 46's `url=url` fix is active in the running build.

Two prior mitigations exist in `web_scraper_adapter.py`:
1. `get_content()` wraps `_get_content_impl()` in `logging.disable(logging.CRITICAL)` / `finally: logging.disable(logging.NOTSET)` (Case File 39 Fix A).
2. `trafilatura.extract(..., url=url, ...)` (Case File 46).

### Environmental Triggers
Fetching URLs whose content trafilatura cannot extract (e.g., Postman documenter pages, JS-rendered API-doc portals) → extraction fails → WARNING logged. The leak additionally requires ≥2 UNCACHED URLs fetched in the SAME parallel batch (`ContextService.get_context()` → `ThreadPoolExecutor(max_workers=5)`, context_service.py:80) with at least one worker exiting its suppression scope (`finally: logging.disable(logging.NOTSET)`) while another worker is still inside `trafilatura.extract()`. Failed extractions are cached as empty-string sentinels (Case 39 Fix B), so each URL leaks at most once per session — matching the user's observation of exactly two leaked lines for two API-doc URLs.

### Ruled Out
- First-party emitter: `git grep -in "discard" -- src tests docs` found no log emitter in `src/` (only comments, unrelated code, and docs).

## Diagnostic Analysis

### Causal Model
1. `trafilatura.bare_extraction()` raises `TypeError/ValueError` when content is not extractable (empty/JS-only pages like Postman documenter / api-doc portals).
2. Its except block emits `LOGGER.warning("discarding data: %s", options.source)`; `options.source` now holds the real URL (Case File 46 fix).
3. `WebScraperAdapter.get_content()` surrounds the entire fetch+extract with `logging.disable(logging.CRITICAL)` … `finally: logging.disable(logging.NOTSET)`. This toggles a PROCESS-GLOBAL, non-thread-safe logging threshold.
4. CONFIRMED (MRE v2, exit 1): `ContextService.get_context()` fetches uncached URLs via `ThreadPoolExecutor(max_workers=5)` (context_service.py:80); each worker calls `get_content()`. Worker A's `finally: logging.disable(logging.NOTSET)` executes while worker B is still inside `trafilatura.extract()`, re-opening the process-global threshold. B's WARNING then passes `Logger.isEnabledFor()` (gated BEFORE any handler is consulted) and propagates. The sequential action path (`ActionFactory`) never leaks because no concurrency overlaps the wrapper.
5. Visibility chain: trafilatura attaches a `NullHandler` to its own logger (`trafilatura/__init__.py:21`), so its records propagate to the root logger; TeDDy's `__main__.py:52` `logging.basicConfig(handlers=[StreamHandler(sys.stderr)])` provides the root handler that prints propagated records to the user's terminal.

### Discrepancies
- Log lines appear while the session was "Waiting for pathfinder to respond..." — scraping is expected during action execution, not while waiting on the LLM. (Resolved: the banner (planning_service.py:39) precedes the planning-window context assembly; `ContextService` fetches uncached context URLs in parallel (context_service.py:80) before the LLM responds. READ actions add URLs to turn context but bypass the session web cache, so their first cached-path fetch happens in the NEXT turn's planning window — matching the user's console excerpt.)
- `get_content()`'s `logging.disable(logging.CRITICAL)` wrapper should suppress trafilatura WARNINGs during extract, yet two "discarding data: <URL>" lines reached the console. (Resolved: process-global `logging.disable` race, empirically proven by MRE v2 Phase C — 5/5 slow-worker warnings escaped after the fast worker's `finally`-restore, while the single-threaded Phase B control was clean.)

### Investigation History
1. (2026-10-01) Hypothesis: emitter is first-party. Observation: `git grep -in "discard"` in src/tests/docs shows no log emitter in `src/`; venv grep pinpoints `trafilatura/core.py:320` `LOGGER.warning("discarding data: %s", options.source)`. Conclusion: third-party emitter confirmed; URL-in-message proves Case File 46 fix active.
2. (2026-10-01) Hypothesis: parallel `get_content()` calls race the process-global `logging.disable` threshold. Observation: MRE v1 (spikes/debug/52-discard-log-race-mre.py, local HTTP server + `redirect_stderr` capture) exited 2 — Phase A found 0 warnings for both served pages. Two instrumentation confounds: (a) trafilatura attaches a NullHandler to its own logger, so bare-process records never reach sys.stderr via lastResort (matches Case File 39 history: "could not reproduce locally due to trafilatura's NullHandler configuration"); (b) v1 discarded the fetch return value, conflating fetch-failure with non-trigger. Conclusion: v1 capture mechanism invalid, trigger unproven; MRE v2 attaches a collecting handler to the `trafilatura` logger, adds a capture-sanity phase (`extract("")`), widens trigger pages, and prints fetched char counts.
3. (2026-10-01) Hypothesis: parallel `get_content()` calls race the process-global `logging.disable` threshold. Observation: MRE v2 exited 1 — [A0] sanity captured exactly 1 record for `extract("")`; [A] `/js` page fetched successfully (0 chars extracted) and triggered `discarding data: .../js`; [B] single-threaded control: 0 warnings; [C] forced 6-worker interleaving: exactly 5/5 slow-worker warnings leaked, 0 from the fast worker — the deterministic finally-restore-race signature. Supporting greps: trafilatura NullHandler confirmed (`__init__.py:21`); terminal visibility via `__main__.py:52` `logging.basicConfig(handlers=[StreamHandler(sys.stderr)])`; the only other racy suppression scope is `WebSearcherAdapter.search()` (web_searcher_adapter.py:111/122). Conclusion: root cause empirically PROVEN — `logging.disable()` is a process-global, non-thread-safe toggle; ContextService's parallel fetching makes one worker's restore race another worker's in-flight extraction. Proceeding to Zero-Touch Shadow verification of a counted-suppression fix.
4. (2026-10-01) Shadow verification + Systemic Audit. Observation: MRE v3 against `spikes/debug/shadow_web_scraper_adapter.py` (counted, lock-guarded suppression scope) exited 0 with 0 leaks under the identical 6-worker interleaving — fix empirically proven without touching `src/`. Categorical audit: `.search(` call-site mapping shows `WebSearcherAdapter.search()` is reachable ONLY via ActionFactory's "research" action (action_factory.py:37, sequential action path) → its identical racy toggle (web_searcher_adapter.py:111/122) is a LATENT race of the same class, not currently firing. Impact audit: `get_text_token_count` is local tiktoken (litellm_adapter.py:229) → ContextService's token-count executor (context_service.py:293) cannot overlap any suppression scope; LiteLLMAdapter's ThreadPoolExecutor serves remote `check_valid_key` calls (litellm_adapter.py:300-305), outside both web adapters' scopes. Conclusion: race class exists in exactly TWO sites (scraper live, searcher latent); systemic fix = shared counted-suppression helper applied to both adapters; purely internal implementation swap, no Port/Signature/DTO changes → no Contract→Migration→Cleanup partitioning required.

## Solution

### Root Cause
`logging.disable()` mutates a single **process-global, non-thread-safe** logging threshold with no thread affinity. `WebScraperAdapter.get_content()` used it as an enter/restore toggle (`logging.disable(logging.CRITICAL)` … `finally: logging.disable(logging.NOTSET)`). During the planning window, `ContextService.get_context()` fetches uncached context URLs through `ThreadPoolExecutor(max_workers=5)` (context_service.py:80), so worker A's `finally` restore re-opened the global threshold while worker B was still inside `trafilatura.extract()`; B's WARNING passed `Logger.isEnabledFor()` (gated before any handler is consulted) and reached the terminal via TeDDy's root `StreamHandler(sys.stderr)` (`__main__.py:52`). Exactly two leaked lines = two uncached non-extractable API-doc URLs in one parallel batch whose failing extractions landed after a sibling's restore; empty-string sentinel caching (Case 39 Fix B) ensures each URL leaks at most once per session.

### Proven Fix
Replace the racy enter/restore toggle with a **counted, lock-guarded suppression scope**: a module-level depth counter guarded by a `threading.Lock`; only the first entrant calls `logging.disable(logging.CRITICAL)` and only the last exiter calls `logging.disable(NOTSET)`. The threshold therefore stays closed until ALL concurrent callers have exited. Empirically verified via Shadow File zero-touch verification: MRE v2 (real adapter) leaked 5/5 slow-worker warnings under forced interleaving; MRE v3 (shadow adapter with the fix) leaked 0/5 under the identical interleaving.

### Systemic Fix Scope (Systemic Audit)
The race class exists in exactly two sites, both fixed by a shared helper (single internal module in `adapters/outbound/`, e.g. `suppressed_logging.py`):
1. `WebScraperAdapter.get_content()` (web_scraper_adapter.py:320/324) — **live** race, firing today via ContextService's parallel URL fetching.
2. `WebSearcherAdapter.search()` (web_searcher_adapter.py:111/122) — **latent** race of the same class: currently only called from ActionFactory's sequential action path, but one refactor away from firing.

No Port/Signature/DTO changes → no Contract→Migration→Cleanup partitioning; purely internal implementation swaps.

### Preventative Measures
- **Supersede Case File 39's guidance:** its preventative measure ("all outbound adapters using noisy libraries should implement `logging.disable(logging.CRITICAL)` suppression") spread the unsafe enter/restore pattern. The corrected systemic rule: suppression scopes in code reachable from concurrent contexts MUST use the counted, lock-guarded helper — never a bare `logging.disable()` enter/restore toggle.
- **Class-level regression test:** a test reproducing the deterministic interleaving (barrier-synchronized concurrent `get_content()` against a slow local HTTP server, asserting zero trafilatura records escape) prevents reintroduction of the pattern in either adapter.
- **Design rule:** process-global interpreter state (logging threshold, warnings filters, locale, cwd) must never be toggled non-atomically from code that can run concurrently; prefer scoped, ref-counted guards.
