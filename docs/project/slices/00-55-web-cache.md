# Slice: Session-Scoped Content Cache for Every Remote Fetch
- **Status:** Planned
- **Milestone:** Ad-hoc (00)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [ContextService](../../architecture/core/services/context_service.md), [WebScraperAdapter](../../architecture/adapters/outbound/web_scraper_adapter.md), [WebScraper](../../architecture/core/ports/outbound/web_scraper.md)
- **Scope Slug:** `web-cache`

## Goal
Put one session-scoped cache behind every surface that fetches a remote resource, so a PDF URL costs one network round trip per session instead of one per READ, per preview, and per turn, and a single transient failure can no longer make a URL render as permanently missing.

## Context
- `ContextService.get_context` is the only surface that caches today. It loads `<session_root>/.web_cache.json` once per assembly (`_load_web_cache`), partitions URLs into cached and uncached, fetches misses on a five-worker `ThreadPoolExecutor`, and persists each fetch through `_save_web_cache` (temp file, then `Path.replace`). Cached hits embed verbatim, because assembly calls the scraper with `truncate=False`.
- The other two surfaces never consult it. `ActionFactory._create_read_action` wraps a `WebReadAction` around `self._scraper.get_content(url=...)` (`action_factory.py:65`), and `textual_plan_reviewer_previews.py:146` calls `app._web_scraper.get_content(resource)` directly. Neither holds a cache handle or a cache directory: `ActionFactory` receives only an `ActionPorts` DTO (shell, filesystem, interactor, web scraper, web searcher, config, PDF extractor), and the preview reads the scraper off the app.
- `_fetch_and_cache_url` persists an empty-string sentinel on every exception and re-raises. `_load_web_cache` validates values as strings, so the sentinel survives reload, and `get_context` then normalizes it to `None`, which `_format_file_section` renders as `--- FILE NOT FOUND ---`. A transient network failure therefore becomes permanent state for the session, and the configured retry budget (`research.max_scraper_retries`, default 3) is never usable again.
- Truncation diverges between paths. Local PDF reads go through `cap_extracted_text` → `truncate_lines(..., action_type="read")`, which appends a truncation notice. Remote reads go through `WebScraperAdapter._truncate_content`, which slices `splitlines()` at the cap and returns silently.
- Cost shape: `_fetch_pdf_bytes` issues `requests.get(url, timeout=5)` with `research.max_scraper_retries` attempts and `2**attempt` backoff, so a failing URL burns roughly 18 seconds before giving up, against 0.3–163 ms to extract the same document once its bytes are local. Network latency, not extraction, is the cost this slice removes.
- Concurrency: the cache dict is shared across the five fetch threads, each mutating it and triggering a whole-dict serialization. A racing save can drop a sibling entry, and serializing a dict a sibling is mutating can raise. Centralizing persistence removes the class instead of patching it.
- Registration sites: `WebScraperAdapter` at `registries/infrastructure.py:110`, `ContextService` at `container.py:233`, and `ActionPorts` constructed at `container.py:103`. Existing cache coverage lives in `tests/suites/unit/core/services/test_context_service_caching.py`.
- `docs/project/specs/context-payload-format.md` specifies payload shape and never mentions caching, so this slice amends no spec. The cache invariant lives in `ARCHITECTURE.md` under "Web Content Cache", which must be rewritten because it currently describes the cache as a `ContextService` detail.

## Scenarios
> As an agent working through a session, I want a remote document I already fetched to stay available without another network round trip, so that a large PDF URL does not cost a full fetch on every turn.

```gherkin
Given a session where the previous turn READ a PDF URL
When the next turn's payload is assembled
Then the document renders as its extracted text from the session cache
And no HTTP request is issued for that URL
```

```gherkin
Given a URL whose first fetch failed
When a later turn assembles a payload containing that URL
Then the fetch is attempted again
And no cached failure marker renders for that URL
```

```gherkin
Given a URL resource selected in the plan reviewer
When its preview renders
Then the preview serves the cached body when present
And a cache miss fetches once and stores the result
```

```gherkin
Given a READ on a PDF URL capped by read.max_lines
When the next turn embeds the same URL
Then the embedded body is the full untruncated text
```

## Edge Cases
- **Truncation boundary**: If a READ caps its return value at `read.max_lines`, then it persists the untruncated body and caps only what it returns, because context assembly embeds cached content verbatim and a truncated cache would silently shrink a later turn's resource.
- **Failure is not state**: If a fetch raises, then nothing is written, because a transient error must cost at most one retry budget rather than the rest of the session.
- **Corrupt cache**: If the cache file is missing, unparseable, or not a flat string-to-string map, then it reads as empty and the fetch proceeds, because cache damage must never block a turn.
- **No session root**: If no session is in scope, as in a session-agnostic `teddy context` export, then fetches run uncached and no file is created, because there is nowhere session-scoped to write.
- **Concurrent writers**: If several fetches complete at once, then each write merges into the on-disk map under one lock rather than replacing it, because a racing save must not drop a sibling entry.
- **Same URL in two scopes**: If a URL appears in both the session and turn scopes, then exactly one fetch serves both, because the cache is keyed by URL alone.
- **Non-PDF payload**: If a URL named `.pdf` returns a body without the `%PDF-` magic bytes, then the fetch fails with `PdfExtractionError` and nothing is cached, because the magic check rejects it before extraction.
- **Empty body**: If a fetch succeeds but yields no text, then the empty body is cached and renders as an empty resource, because a successful empty response is a fact rather than a failure, and the previous `--- FILE NOT FOUND ---` rendering for that case disappears with the sentinel.
- **Announced truncation**: If remote content exceeds `read.max_lines`, then the cut carries the same notice a long local file receives, because silent truncation violates Failure Transparency.

## Key Unknowns

- [ ] `[Technical]` Session-scope handoff: `ActionFactory` and the plan reviewer hold no session root, so the cache must learn it either by being bound per turn at the composition root, by receiving a `session_root` argument on each call, or by resolving it through the session manager. Design Sensitivity: if bound per turn, `ActionPorts` and the reviewer gain a dependency while fetch-call signatures stay unchanged; if passed per call, every fetch surface's signature and caller tests change; if resolved through the session manager, the cache adapter takes on a filesystem lookup it does not own.
- [ ] `[Technical]` Write ownership: whether the adapter performs a locked read-modify-write per save, or callers merge and the adapter only writes a supplied map. Design Sensitivity: if the adapter owns the merge, saving one URL is the whole contract and the shared mutable dict disappears; if callers merge, the racing-save defect survives and must be fixed elsewhere.
- [ ] `[Functional]` Failure rendering: with no negative sentinel, a URL that fails during a READ shows what in the action log and in the next payload, namely the existing `--- FILE NOT FOUND ---` marker, an explicit fetch-failure marker, or a fresh attempt each turn. Design Sensitivity: if a distinct marker is wanted, `_format_file_section` gains a second missing state and the payload spec's `Resource Contents` wording needs review; if the existing marker stays, no formatting changes at all.
- [ ] `[Harness]` Deterministic three-surface coverage: proving cache reuse from context assembly, the READ action, and the reviewer preview without global patching or real network needs an in-memory fake cache plus an injected fake scraper per surface, and the preview branch must be driven under a forced terminal per the architecture's terminal-gate rule. Design Sensitivity: if the preview cannot be driven deterministically, that surface is covered at adapter level only and the slice records the gap.

## Impact
1. `[NEW]` Session-scoped content cache port in `core/ports/outbound/` — the read and save contract for URL-keyed session content, including the untruncated-body invariant and the absent-session behavior. Naming follows the surrounding port convention and is settled by the Architect.
2. `[NEW]` Filesystem cache adapter in `adapters/outbound/` — `.web_cache.json` under the session root, atomic temp-then-replace write, locked merge, tolerant load, no TTL, intra-session only.
3. `[EXTEND]` `WebScraperAdapter._truncate_content` — route the cap through the shared announced helper instead of a silent line slice, leaving the lazy imports and the retry budget untouched.
4. `[MIGRATE]` `ContextService` — delete `CACHE_FILENAME`, `_load_web_cache`, `_save_web_cache`, and the empty-sentinel normalization; read once per assembly through the port, fetch misses in parallel, persist successes only.
5. `[MIGRATE]` `ActionFactory` READ-on-URL wrapper at `action_factory.py:65` — consult the cache, fetch on a miss, persist the untruncated body, return the capped body.
6. `[MIGRATE]` `textual_plan_reviewer_previews.py:146` — serve previews from the cache under the same miss-then-store rule.
7. `[MIGRATE]` Composition root — `container.py` and `registries/infrastructure.py` register the adapter and thread it into `ContextService`, `ActionPorts`, and the plan reviewer.
8. `[PRUNE]` The per-surface ad-hoc cache plumbing once all three surfaces use the port, so no private cache helper remains inside a core service.
9. Explicitly out of scope: bounding embedded PDF text by size, TTL and expiry, cross-session sharing, eviction policy, and any change to what a cache hit embeds.
10. Documentation: `ARCHITECTURE.md`'s "Web Content Cache" bullet and its Component Map rows are rewritten by the Architect to describe the port and adapter rather than a `ContextService` detail, with a component doc for the new port created in the same pass.

## Deliverables

- [ ] **Interface** - Define the session-scoped content cache port: reading returns cached content or nothing, saving persists one URL's untruncated body, and the contract states how an absent session behaves.
- [ ] **Harness** - Add an in-memory fake cache and the fixture wiring that lets each surface be driven without network or disk.
- [ ] **Wiring** - Register the cache adapter at the composition root and thread it into `ContextService`, `ActionPorts`, and the plan reviewer with the previous behavior intact apart from this slice's stated changes.
- [ ] **Core** - Migrate `ContextService` to the port: one read per assembly, parallel misses, successes persisted only, sentinel normalization removed.
- [ ] **Adapter** - Implement the filesystem cache with atomic writes, a locked merge, tolerant load, and session-root resolution.
- [ ] **Migration** - Route READ-on-URL and the reviewer preview through the cache, unify remote truncation on the announced helper, and update the affected caller tests.
- [ ] **Cleanup** - Remove the private cache helpers and the silent line slice once no caller remains.

## Implementation Notes
Not started.

## Verification
1. **Cache written at READ time:**
   Start a session and `READ` a PDF URL.
   Verify `.teddy/sessions/<session>/.web_cache.json` exists and contains that URL once the action completes.
2. **No refetch on the next turn:**
   Continue one turn with the same URL in scope while the network is unavailable.
   Verify the payload still renders the document text rather than a missing marker.
3. **Failure is not persisted:**
   `READ` an unreachable URL such as `https://example.invalid/report.pdf`.
   Verify the cache file holds no entry for it, and that the next turn attempts the fetch again instead of rendering `--- FILE NOT FOUND ---`.
4. **Announced truncation:**
   Set `read.max_lines: 5` in `.teddy/config.yaml` and `READ` a PDF URL whose text layer exceeds five lines.
   Verify the result ends with the same truncation notice a long local file shows.
5. **Untruncated cache:**
   After the capped READ from step 4, continue one turn.
   Verify the payload embeds more than five lines, proving the cache kept the full body.
