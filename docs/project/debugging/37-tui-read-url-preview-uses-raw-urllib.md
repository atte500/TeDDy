# Bug: TUI READ URL Preview Uses Raw urllib Instead of Existing Web Scraper
- **Status:** Resolved
- **Milestone:** [Milestone 4: TUI & UX Enhancements](/docs/project/milestones/04-tui-ux-enhancements.md)
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

Pressing `e` on a READ action whose resource is a URL (e.g., `https://example.com/file.md`) opens a temporary file containing **raw HTML** (or fails entirely with a network/403 error). The user expects the URL page to be scraped into readable Markdown, matching the behavior of READ actions executed at runtime.

Commit `1fee80b1` added `_fetch_url_content()` using `urllib.request.urlopen()` directly. That approach:
1. Returns raw HTML, not extracted Markdown — the temp `.md` file is filled with `<html><head>...` markup.
2. Lacks the stealth User-Agent rotation, retries, 403 handling, and trafilatura extraction implemented in `WebScraperAdapter`.
3. Is blocked by many sites that the existing scraper bypasses.

**Expected:** READ URL preview opens a temp `.md` file containing the extracted Markdown content (same as runtime READ URL fetching via `IWebScraper`).
**Actual:** Raw HTML or fetch failure.

**Minimal reproduction:**
1. Create/edit a plan with a READ action whose resource is `https://example.com`.
2. Press `e` in the TUI.
3. Observe the temp file content: raw HTML instead of `# Example Domain ...`.

## Context & Scope

### Regressing Delta
Commit `1fee80b1` (`fix(tui): fetch URL content for READ preview and skip ConfirmScreen for GUI editors`) added `_fetch_url_content()` in `src/teddy_executor/adapters/inbound/textual_plan_reviewer_previews.py` using `urllib.request.urlopen()`, writing the raw response into a `.md` temp file. The project already had a battle-tested `IWebScraper` port (`WebScraper` Protocol -> `WebScraperAdapter`, trafilatura-based, UA rotation, GitHub handling, retries) used at runtime. The new code bypassed the existing port.

### Environmental Triggers
- READ action with `resource`/`path` set to an `http://` or `https://` URL.
- Occurs regardless of the configured editor (CLI or GUI).

### Ruled Out
- Local file READ actions (unchanged — they open the real file correctly).
- Editor configuration/launch itself (the editor opens; only the fetched content is wrong).

## Diagnostic Analysis

### Causal Model
`preview_readonly()` currently -> `_fetch_url_content(resource)` -> `urllib.request.urlopen()` -> raw HTML decoded as text -> written to `teddy_read_url_*.md` temp file -> opened in editor. The `IWebScraper` port (`WebScraperAdapter`, used by `ContextService` and `ActionFactory` at runtime) is NOT invoked because `ReviewerApp` has no reference to it.

**Planned fix:** (1) Constructor-inject `IWebScraper` into `TextualPlanReviewer` -> `ReviewerApp` (`self._web_scraper`); (2) wire `web_scraper=container.resolve(IWebScraper)` in `registries/reviewer.py::tui_factory`; (3) replace the URL branch in `preview_readonly()` with `app._web_scraper.get_content(resource)` and write the extracted Markdown to the temp `.md` file; (4) remove `_fetch_url_content` / `urllib.request` usage. Verification via shadow replica before touching `src/`.

### Discrepancies
- (Resolved: MRE probe, Turn 40) `_fetch_url_content()` uses raw `urllib.request.urlopen()`: on `https://example.com` it returned 559 chars of raw HTML starting `<!doctype html>...`. The existing `WebScraperAdapter.get_content()` returned 113 chars of extracted Markdown (`This domain is for use in documentation examples...`). The READ URL preview path bypasses the battle-tested `IWebScraper` port.
- (Resolved: shadow verification, Turn 41) Replacing the URL branch with `app._web_scraper.get_content(resource)` writes the scraper's Markdown into the editor temp file — all four shadow probe assertions passed.

### Investigation History
1. **Turn 36 (2026-08-30):** User reports "the URL fetching doesn't work", asks to use the existing logic that would actually scrape the URL page.
2. **Turn 37 (2026-08-30):** Confirmed port exists: `WebScraper.get_content(url, **_kwargs) -> str` returns Markdown; `WebScraperAdapter` implements stealth UA rotation + trafilatura. `ReviewerApp.__init__` does NOT accept a scraper dependency. `_fetch_url_content()` uses raw urllib.
3. **Turn 40 (2026-08-30):** MRE probe executed (`spikes/debug/37-mre-url-scrape.py`) — **BUG CONFIRMED**: `_fetch_url_content("https://example.com")` returned 559 chars of raw HTML (`<!doctype html><html lang="en">...`); `WebScraperAdapter().get_content(...)` returned 113 chars of extracted Markdown (`This domain is for use in documentation examples...`). Wiring map completed:
   - Runtime `get_content` callers: `core/services/action_factory.py:62`, `core/services/context_service.py:74`.
   - `ReviewerApp` constructed at `adapters/inbound/textual_plan_reviewer.py:65` (production) plus 25 test sites.
   - `IWebScraper` is registered in `container.py` and resolvable; `registries/reviewer.py::tui_factory()` is the reviewer composition root.
4. **Turn 41 (2026-08-30):** Created shadow replica `spikes/debug/shadow_textual_plan_reviewer_previews.py` with the URL branch routed through `app._web_scraper.get_content()` (zero-touch), plus probe `spikes/debug/37-shadow-verify.py`. Shadow probe **PASSED** — all four assertions held (scraper port consulted, editor launched with teddy_read_url_*.md, Markdown content written, temp file cleaned up).
5. **Turn 42 (2026-08-30):** Alignment gate passed — user approved the 5-file fix plan ("ok proceed").
6. **Turn 43 (2026-08-30):** Implementation part 1: `ReviewerApp` accepts `web_scraper` (default None → `self._web_scraper`); `preview_readonly()` URL branch routed through `app._web_scraper.get_content()` with raw urllib removed; URL tests updated to mock the port; new "no web scraper configured" regression test added. Pending: `TextualPlanReviewer.__init__` + container wiring in `registries/reviewer.py::tui_factory`.
7. **Turn 44 (2026-08-30):** Implementation part 2 (DI wiring complete): `TextualPlanReviewer.__init__` accepts `web_scraper` (default None) and forwards it to `ReviewerApp(...)`; `registries/reviewer.py::tui_factory` resolves `IWebScraper` from the container. Verification: full inbound adapter suite **141 passed**; integration core services suite **58 passed** (includes `test_reviewer_wiring.py` and `test_container_wiring.py`). The targeted multi-file run initially reported exit code 5 ("no tests ran") — false negative caused by a path typo (`tests/suites/unit/ports/inbound/...` vs the actual `tests/suites/unit/core/ports/inbound/...`); corrected re-run passes.

## Solution

### Root Cause
Commit `1fee80b1` introduced `_fetch_url_content()` in `textual_plan_reviewer_previews.py` using raw `urllib.request.urlopen()`. This approach:
1. Returned raw HTML (e.g., `<!doctype html>...` for `https://example.com`) instead of extracted Markdown.
2. Lacked the stealth User-Agent rotation, retry logic, 403 handling, and trafilatura extraction already implemented in the existing `IWebScraper` port (`WebScraperAdapter`).
3. Bypassed the battle-tested port used at runtime by `ActionFactory` and `ContextService`, so READ URL preview behavior diverged from runtime READ URL behavior.

### Fix
The READ URL preview path now routes through the existing `IWebScraper` port via strict Constructor Injection:
1. `registries/reviewer.py::tui_factory` resolves `IWebScraper` from the container and passes it to `TextualPlanReviewer`.
2. `TextualPlanReviewer.__init__` accepts `web_scraper` (default `None`) and forwards it to `ReviewerApp`.
3. `ReviewerApp.__init__` accepts `web_scraper` (default `None`) → `self._web_scraper`.
4. `preview_readonly()` URL branch calls `app._web_scraper.get_content(resource)` and writes the extracted Markdown to a `teddy_read_url_*.md` temp file; it notifies the user when no scraper is configured, when the fetch fails, or when no content is extracted.
5. `_fetch_url_content()` / `urllib.request` fully removed from the inbound adapter.

The new `web_scraper` parameter defaults to `None` on both `TextualPlanReviewer` and `ReviewerApp`, so all existing construction sites remain backward-compatible.

### Preventative Measures
This fix addresses the class of "new code bypassing an existing outbound port" bugs. The Systemic Audit grep confirmed no other inbound adapter uses raw `urllib`/`requests`; the port-based path now mirrors runtime READ URL behavior exactly (`ActionFactory`/`ContextService` use the same `IWebScraper`). Future TUI preview features must reuse the injected ports rather than introducing ad-hoc network calls.
