# Bug: Web Cache Persisted a Failed Fetch as a Missing Document
- **Status:** Resolved
- **Milestone:** Ad-hoc (00)
- **Vertical Slice:** [Session-Scoped Content Cache for Every Remote Fetch](../slices/00-55-web-cache.md)
- **Specs:** None

## Symptoms
A remote resource whose first fetch failed rendered as a permanently missing document for the rest of the session. Expected: the next turn retried the URL and reported its own outcome. Actual: every later payload embedded the same empty result, so a transient network error became durable state and the configured retry budget was never usable again.

Reproduction: within one session, request a URL that cannot be reached (for example `https://example.invalid/report.pdf`), then assemble a payload containing it again on the following turn. The second turn issued no request and rendered the document as missing.

## Context & Scope
### Regressing Delta
The behavior lived in `ContextService`'s private web cache path: `_fetch_and_cache_url` stored an empty-string sentinel in `<session_root>/.web_cache.json` on every fetch exception and re-raised, while `_load_web_cache` accepted the sentinel because it only validated that values were strings. `get_context` then normalized the empty string to `None`, which `_format_file_section` rendered as `--- FILE NOT FOUND ---`.

### Environmental Triggers
None. The behavior reproduced on every platform with any configured provider, and required only one failed fetch followed by one later assembly.

### Ruled Out
- Provider configuration: the sentinel path was reached before any provider-specific handling, and reproduced with a deliberately invalid hostname.
- URL-based truncation: `read.max_lines` affected neither what was written nor how a stored value was interpreted.

## Diagnostic Analysis
### Causal Model
The cache stored a negative result alongside successful bodies. Because the loader only distinguished "value is a string" from "value is not a string", a stored sentinel was indistinguishable from a fetched body, so the miss branch never ran again for that URL within the session.

### Discrepancies
- [x] Discrepancy between expected and observed behavior (Resolved: the cache stored fetch failure as content, and the reader had no way to tell a sentinel from a body).

### Investigation History
1. Investigated whether the failure was re-fetched by inspecting the on-disk cache after a failed fetch; observed the URL present with an empty value, which proved the failure itself was being persisted.
2. Investigated whether the loader rejected that value by reading `_load_web_cache`; observed it accepted any string, which explained why the miss branch never ran again.

## Solution
### Root Cause
A failed fetch was written into the session cache as an empty string, and the reader could not distinguish that sentinel from a successfully fetched empty body. The fix removes the sentinel rather than special-casing it: only successful fetches are stored, so a failed URL leaves no entry and is retried on the next turn.

### Affected Components
- `WebContentService`: owns the cached-fetch workflow for every remote surface and persists only successful bodies, mapping a failed batch fetch to `None` for the caller to render as missing.
- `IWebContentCache` / `WebContentCacheAdapter`: the cache contract states that absence means "not fetched yet", never "fetch failed", so no negative marker has a place to live.
- `ContextService`: stopped reading and writing the cache itself; a failed URL now renders the existing missing marker and is retried next turn.
- `ActionFactory` and `textual_plan_reviewer_previews`: both remote surfaces resolve through the coordinator, so no path can reach the scraper without the successes-only rule.
- `TestCacheFailureRegression` and `TestLoadWebCache` / `TestSaveWebCache` in `tests/suites/unit/core/services/test_context_service_caching.py`: deleted with the private helpers they pinned, because they asserted the sentinel behavior this fix reverses. The replacement coverage lives in `tests/suites/unit/core/services/test_web_content_service.py` (`test_batch_maps_a_failed_url_to_none_and_merges_only_successes`, `test_failed_fetch_propagates_and_merges_nothing`) and in `tests/suites/acceptance/test_web_content_cache_wiring.py` (`test_failed_fetch_renders_the_missing_marker_and_merges_nothing`).

## Note on Bug Numbering
This bug number also covers an unrelated point about suppressed scraper logging, which keeps its own regression coverage in `tests/suites/unit/adapters/outbound/test_web_scraper_resilience.py` and is untouched by this fix.
