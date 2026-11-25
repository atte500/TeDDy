# Slice: Session-Scoped Content Cache for Every Remote Fetch
- **Status:** In Progress
- **Milestone:** Ad-hoc (00)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [IWebContentCache](../../architecture/core/ports/outbound/web_content_cache.md), [WebContentService](../../architecture/core/services/web_content_service.md), [WebContentCacheAdapter](../../architecture/adapters/outbound/web_content_cache_adapter.md), [ContextService](../../architecture/core/services/context_service.md), [ActionFactory](../../architecture/core/services/action_factory.md), [ActionPorts](../../architecture/core/domain/action_ports.md), [ActionDispatcher](../../architecture/core/services/action_dispatcher.md), [ExecutionOrchestrator](../../architecture/core/services/execution_orchestrator.md), [TextualPlanReviewer](../../architecture/adapters/inbound/textual_plan_reviewer.md), [WebScraperAdapter](../../architecture/adapters/outbound/web_scraper_adapter.md), [WebScraper](../../architecture/core/ports/outbound/web_scraper.md)
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
- `docs/project/specs/context-payload-format.md` specifies payload shape and never mentions caching, so this slice amends no spec. The cache invariant lives in `ARCHITECTURE.md` under "Web Content Cache", rewritten in the design phase to describe the port and adapter instead of a `ContextService` detail.
- **Resolved — session-scope handoff:** `ActionExecutor.confirm_and_dispatch` → `ActionDispatcher.dispatch_and_execute` → `execute(**execution_params)` forwards only plan params, and `ActionData` carries no session field, so nothing session-scoped reaches a READ today. `ExecutionOrchestrator` holds `plan.plan_path` (`plan.py:77`) and already forwards plan-level facts (`agent_name`, `is_session`), so an optional `session_root` keyword travels that same route into `IActionFactory.create_action`. The reviewer needs no plumbing: `ReviewerApp.project_context.session_root` is already read by the reviewer helpers.
- **Resolved — write ownership:** the adapter owns a locked read-modify-write merge, so a save names only the URLs it fetched and never replaces a sibling entry. The port therefore exposes `load_entries` / `merge_entries` rather than per-URL get/put: assembly fetches a batch, and per-URL reads would parse the same JSON once per URL per turn.
- **Resolved — failure rendering:** after the migration no negative sentinel exists, so a failed URL renders the existing `--- FILE NOT FOUND ---` marker and is retried on the next turn. The payload format needs no change.
- **Resolved — harness:** the project convention is `tests/harness/setup/fake_<port>.py` implementing the port (as `FakeLlmClient(ILlmClient)` does). `_resolve_read_resource` is a plain sync function over an injected app with no existing coverage, so the preview surface is drivable without a terminal.
- **Resolved — truncation:** `truncate_lines(content, max_lines, direction="tail", hint="", action_type=None)` is the single announced helper, and `cap_extracted_text` wraps it with `direction="head", action_type="read"`. `WebContentService` becomes its only remote caller, so the adapter's private `_truncate_content` and the port's `truncate` flag are pruned rather than corrected: one owner applies the cap, and no surface can reach a silent line slice.
- **Redundant parameter:** `cache_dir` on `get_context` always equals `session_root` at every call site (`planning_service.py:90-97`, `session_orchestrator.py:477-496`), so it is pruned and `session_root` stays the single scope handle.

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
- **Cache write failure**: If a merge cannot be persisted, then the fetched body is still returned and the failure is logged, because discarding a completed fetch over a cache write is the worse outcome.
- **Same URL in two scopes**: If a URL appears in both the session and turn scopes, then exactly one fetch serves both, because the cache is keyed by URL alone.
- **Non-PDF payload**: If a URL named `.pdf` returns a body without the `%PDF-` magic bytes, then the fetch fails with `PdfExtractionError` and nothing is cached, because the magic check rejects it before extraction.
- **Empty body**: If a fetch succeeds but yields no text, then the empty body is cached and renders as an empty resource, because a successful empty response is a fact rather than a failure, and the previous `--- FILE NOT FOUND ---` rendering for that case disappears with the sentinel.
- **Announced truncation**: If remote content exceeds `read.max_lines`, then `WebContentService` cuts it through the shared helper so the cut carries the same notice a long local file receives, because silent truncation violates Failure Transparency.

## Key Unknowns
None remaining. All four unknowns were resolved during discovery and are recorded under Context: the session root travels as an optional keyword from the orchestrator, the adapter owns the locked merge, a failed fetch leaves no entry and keeps the existing missing marker, and the three surfaces are covered by an in-memory cache fake plus an injected fake scraper.

## Impact
1. `[NEW]` `IWebContentCache` in `core/ports/outbound/` — the stateless read and merge contract for URL-keyed session content, keyed by an explicitly passed `session_root`, including the untruncated-body and absent-session rules.
2. `[NEW]` `WebContentService` in `core/services/` — the coordinator owning the single (`fetch_one`) and batch (`fetch_many`) cached-fetch workflows, so the store-verbatim/cap-only-on-return rule exists once rather than per surface.
3. `[NEW]` `WebContentCacheAdapter` in `adapters/outbound/` — `.web_cache.json` under the session root, atomic temp-then-replace write, locked merge, tolerant load, no TTL, intra-session only.
4. `[NEW]` `WebContentCacheError` in `core/domain/models/exceptions.py` — inherits from `TeddyError`, so the coordinator catches this specific type and still returns the fetched body.
5. `[PRUNE]` `WebScraper.get_content`'s `truncate` flag and `WebScraperAdapter._truncate_content` — the adapter returns the verbatim body and `WebContentService` owns the announced cap, so the second truncation owner disappears instead of being corrected in place. Pruned only after the three surfaces migrate; the lazy imports and the retry budget stay untouched.
6. `[EXTEND]` `IActionFactory.create_action` / `ActionFactory.create_action` — add an optional `session_root` keyword so a READ-on-URL is built already knowing its cache scope; existing two-argument callers stay valid.
7. `[MIGRATE]` `ContextService` — delete `CACHE_FILENAME`, `_load_web_cache`, `_save_web_cache`, `_fetch_and_cache_url`, the fetch pool, and the empty-sentinel normalization; resolve the URL scope through one `fetch_many` call and drop the redundant `cache_dir` parameter.
8. `[MIGRATE]` `ActionFactory._create_read_action` — bind `WebContentService.fetch_one` with the creation-time session root instead of the scraper, so the handler never decides truncation.
9. `[MIGRATE]` `textual_plan_reviewer_previews._resolve_read_resource` — serve URL previews through the coordinator with `project_context.session_root`, keeping the existing empty-content notice.
10. `[MIGRATE]` `ExecutionOrchestrator` → `ActionExecutor.confirm_and_dispatch` → `ActionDispatcher.dispatch_and_execute` — thread one optional `session_root`, derived from `plan.plan_path` through the shared helper, following the existing `agent_name`/`is_session` convention rather than a new channel. `ActionExecutor` carries mile zero of that pass-through but holds no component design, so the contract is documented at the orchestrator and dispatcher boundaries and the gap is not papered over with a phantom link.
11. `[MIGRATE]` `ActionPorts` — drop the now-dead `web_scraper` field so the bundle cannot offer a second, uncached path to remote content; the coordinator arrives at the factory as a separate keyword because a `core/domain/models/` DTO must not name a `core/services/` class.
12. `[MIGRATE]` Composition root — register the adapter and the coordinator, thread them into `ContextService`, `ActionFactory`, and the plan reviewer, and drop the `ActionPorts` scraper argument at `container.py:103`.
13. `[REFACTOR]` Session-root derivation at the touched call sites — one helper in `core/utils/paths.py` replaces the hand-rolled `Path(...).parent.parent` in `planning_service`, in `session_orchestrator`'s context assembly, and in the new dispatch-time derivation in `execution_orchestrator`, rather than adding a fourth copy; unrelated occurrences stay untouched. `SessionOrchestrator` and `PlanningService` only adopt the helper, so their contracts are unchanged and their designs need no edit.
14. `[PRUNE]` The superseded expectations — the per-surface cache plumbing, the `cache_dir` parameter and its port-contract tests, the adapter's own truncation tests, which move to the coordinator's suite with the announced notice they must now assert, and the Bug 39 cache-failure tests, whose reversal is recorded in that bug's case file rather than left as a silent deletion.
15. Explicitly out of scope: bounding embedded PDF text by size, TTL and expiry, cross-session sharing, eviction policy, and any change to what a cache hit embeds.
16. Documentation: `ARCHITECTURE.md`, the six affected component designs, and the three new component designs are written by the Architect in the same pass.

## Deliverables

- [x] **Env** - Extend `.githooks/check_architecture_boundaries.py` so the `.web_cache.json` literal is owned by the adapter alone, failing the check when it appears outside the cache adapter module and `tests/`.
- [x] **Interface** - Define `IWebContentCache` with `load_entries` / `merge_entries` keyed by an optional `session_root`, and add `WebContentCacheError` under `TeddyError`, with no caller changed yet.
- [x] **Harness** - Add `FakeWebContentCache` and `FakeWebScraper` under `tests/harness/setup/` plus the fixture wiring that drives all three surfaces without network or disk.
- [x] **Wiring** - Register the adapter and `WebContentService` at the composition root and route context assembly through the coordinator with the previous behavior intact apart from this slice's stated changes.
- [x] **Core** - Implement `WebContentService`: one map load per batch, parallel misses, verbatim store, announced cap for a capped read, successes-only persistence, and a tolerated cache-write failure.
- [ ] **Adapter** - Implement `WebContentCacheAdapter` with atomic writes, a locked merge, tolerant load, and the absent-session no-op.
- [ ] **Migration** - Route READ-on-URL through the coordinator with the session root threaded from the orchestrator into `create_action`, serve the reviewer preview from `project_context.session_root`, unify the remote cap on `truncate_lines`, drop `ActionPorts.web_scraper` and the `cache_dir` parameter, adopt the shared session-root helper at the touched call sites, and update the affected caller tests.
- [ ] **Cleanup** - Remove the private cache helpers, the fetch pool, the sentinel normalization, the `truncate` flag with `_truncate_content`, and the superseded cache-failure and adapter truncation tests once no caller remains, recording the Bug 39 reversal in its case file.

## Implementation Notes

### Env — Cache filename ownership ratchet
- `check_architecture_boundaries.py` now names `src/teddy_executor/adapters/outbound/web_content_cache_adapter.py` as the single owner of the `.web_cache.json` literal and reports a violation for any other `src/`, `scripts/`, or `tests/` Python file that holds it. `tests/` is exempt by design, because the adapter's own suite has to assert on the filename it writes.
- The rule ships with one sanctioned legacy holder, `src/teddy_executor/core/services/context_service.py`, since the adapter does not exist yet. The Cleanup deliverable prunes `_WEB_CACHE_FILENAME_LEGACY_OWNERS` together with the private cache helpers, and ownership becomes absolute at that commit.
- Enforcement path is unchanged: the existing `check-architecture-boundaries` entry already runs this script over `^(src|scripts|tests)/` for `types: [python]` at the `manual` stage, so the quality job picks the rule up without new wiring.
- The checker is string-based rather than AST-based on purpose: it guards a filename literal, which may appear in code, in a docstring, or in a path fragment, and any of those occurrences is a second owner.
- Verified with three probes: a module outside the adapter exits 1 with a violation naming the adapter, the adapter path exits 0, and the tracked tree reports zero cache-literal violations.
- Unrelated pre-existing findings surfaced by the repository-wide run: six `_FORBIDDEN_CORE_ADAPTER_LIBS` violations (`yaml` in `init_service`, `prompt_manager`, `session_lifecycle_manager`, `session_repository`; `typer` in `session_orchestrator` and `core/utils/terminal.py`). Not introduced by this slice, the hook stays non-blocking, and Milestone 05 already owns the reconciliation.
- Full suite green with the hook edit in place: 2584 passed, 5 skipped.
- No design-doc change was required: the cache adapter's design already states that the filename literal lives in that module and in its tests alone, which is now enforced rather than merely documented.

### Interface — Cache port and error
- `IWebContentCache` lives in `core/ports/outbound/web_content_cache.py` as a `@runtime_checkable` `typing.Protocol`, matching the nearest precedent `IPdfExtractor` and the Protocol majority among outbound ports. It declares `load_entries(session_root) -> dict[str, str]` and `merge_entries(session_root, entries) -> None`, both taking the session root explicitly: the port answers "which session", the adapter alone answers "where on disk".
- The `ABC` idiom was deliberately not used, even though `test_llm_client_contract.py` relies on `Abstract-Class TypeError` for `ILlmClient`. `ILlmClient` predates the Protocol convention; every port added beside it is a `runtime_checkable` Protocol, and the design doc specifies that shape. The contract test therefore asserts structural conformance rather than instantiation failure, and records that choice here rather than leaving it implicit.
- `WebContentCacheError(message, session_root)` sits in `core/domain/models/exceptions.py`, inheriting `TeddyError` and carrying the failing root as a constructor-followed attribute — the exact shape of `PdfExtractionError(message, source)`. It is not re-exported from the ports package, matching `PdfExtractionError`, which is imported from its domain module everywhere.
- The port is re-exported through `core/ports/outbound/__init__.py` and registered in `__all__`, so callers import it like every sibling port. This mattered for the Red step: without the re-export the module would exist but the package import would still fail.
- Red evidence: `ImportError: cannot import name 'IWebContentCache' from 'teddy_executor.core.ports.outbound'` and `ImportError: cannot import name 'WebContentCacheError' from 'teddy_executor.core.domain.models.exceptions'`, both collection errors, so neither test passed vacuously.
- Green evidence: 6 tests pass across `tests/suites/unit/core/ports/outbound/test_web_content_cache_contract.py` (conforming fake matches, merge-less partial does not, both members declared) and `tests/suites/unit/core/domain/models/test_web_content_cache_error.py` (inherits `TeddyError`, carries the session root). Full suite green at 2590 passed, 5 skipped.
- Additive constraint honored: no container registration, no `ActionPorts` field change, and no context-assembly routing was touched. The port has no production caller yet, which is exactly what the Interface deliverable requires.
- Pre-existing finding while reading `exceptions.py`: five siblings still inherit bare built-ins — `SearchTextNotFoundError(ValueError)`, `FileAlreadyExistsError(FileExistsError)`, `MultipleMatchesFoundError(Exception)`, `WebSearchError(Exception)`, `ConfigurationError(Exception)` — contrary to the `TeddyError` root rule. Not introduced here; Milestone 06 already owns "unify custom exceptions". `WebContentCacheError` follows the mandated root, so the new artifact does not add to that debt.

### Harness — In-memory cache and scraper fakes
- Two standalone fakes under `tests/harness/setup/`, matching `FakePdfExtractor` (a plain class holding scripted values and recording calls) and deliberately not the spec-bound mock idiom: `mock_scraper` stays `register_mock(container, IWebScraper)`, a `POSIXPathMock(spec=...)`. The two idioms serve different jobs, so no existing double was duplicated and none was converted.
- `FakeWebContentCache(entries=None, merge_error=None)` holds a URL-keyed map, records `load_calls` (one entry per requested root) and `merge_calls` (root plus the merged batch), hands back a copy so a caller cannot mutate the store by accident, and mirrors the port's absent-session rule: a `None` root reads empty and accepts no merge.
- The scripted `WebContentCacheError` raises *before* the map update, because the adapter's contract says a failed merge leaves the stored map as it was. A fake that mutated first would let the later tolerated-write-failure test prove the opposite of the invariant it exists to guard.
- `FakeWebScraper(contents=None, failures=None)` records every call as `(url, truncate, kwargs)`, so the Core deliverable can prove the coordinator never asks the scraper to truncate, and rejects an unscripted URL through a native assertion naming it: a silent empty default body would let a mis-scripted test pass.
- Both accept the current `WebScraper` signature including `truncate: bool = True`. That flag is pruned only in Cleanup, so recording it now is what keeps the verbatim-store edge case observable when Core lands.
- Fixtures follow the uniform idiom — import the port and the fake inside the body, construct, `container.register(<Port>, instance=fake)`, return — and are wired through the same three touch points as every other fake: definitions in `tests/harness/setup/mocks.py`, re-export in `tests/harness/setup/composition.py`, import plus `__all__` entry in `tests/conftest.py`.
- `fake_web_scraper` and `mock_scraper` register the same `IWebScraper` port on one container, so a test must request one fixture or the other; whichever resolves last wins. Documented on the fixture itself and here rather than left as a silent trap.
- Red evidence: `ModuleNotFoundError: No module named 'tests.harness.setup.fake_web_content_cache'` and the same for `fake_web_scraper`, both collection errors, so no test passed vacuously.
- Green evidence: 13 tests pass across `tests/suites/unit/test_fake_web_content_cache_harness.py` (7) and `tests/suites/unit/test_fake_web_scraper_harness.py` (6), covering scripting, call recording, the absent-session rule, the intact-map-on-failure rule, the recorded `truncate` flag, the scripted raise, the unscripted-URL rejection, `isinstance` conformance to both ports, and fixture registration. Full suite green at 2603 passed, 5 skipped.
- Additive constraint honored: no production module imports a fake, no real adapter was registered, and `ActionPorts` is untouched. The fakes are reachable only from tests, which is exactly what the Harness deliverable requires.
- No component design doc was created for the fakes: `FakePdfExtractor` and `FakeLlmClient` have none either, and the Component Map's Test Harness table lists only drivers, observers, and shared scenario modules. The harness's own contract is its unit tests.

### Harness — Post-commit gate flake repair
- The first Harness commit was reverted by the unskippable post-commit gate: `test_validator_edit_performance_large_file` asserted a 0.1s **wall-clock** budget, and under eight xdist workers a 13ms matcher measured 114ms. Five isolated runs passed beforehand, so the assertion was healthy on an idle machine and the failure was worker contention, not algorithmic cost.
- Repaired in `e8fea432` (`fix(tests): measure the validator budget in thread cpu time`) as a Local Flaw per the Integration rule: the test now measures `time.thread_time()`, so worker descheduling and background threads cannot inflate the number, while a genuine 15-20s algorithmic regression still reports as seconds of CPU and trips the guard.
- A zero-budget probe measured `0.0136s` of CPU time, roughly seven times the headroom of the restored 0.1s budget. Two consecutive full-suite runs passed at the pre-Harness baseline of 2590.
- The `GITHUB_ACTIONS` skipif on that test was deliberately left untouched; revisiting CI exposure is a separate decision and not this slice's to make.

### Wiring — Coordinator, adapter, and context assembly
- `WebContentService` (`core/services/web_content_service.py`) arrives with `fetch_many` only: one `load_entries` call per batch, one verbatim `get_content(url, truncate=False)` per uncached URL, one `merge_entries` batch for the successes, and `None` for a URL whose fetch raised. `fetch_one` is absent on purpose, because its announced cap is one of Core's own edge cases.
- `WebContentCacheAdapter` (`adapters/outbound/web_content_cache_adapter.py`) lands as a draft that already honors the invariants the acceptance tests pin: it owns the `.web_cache.json` filename and the flat URL-to-body map, reads tolerantly, and treats a `None` session root as a no-op. The locked merge, the atomic temp-then-replace write, and the write-failure translation are Adapter's deliverable; this draft writes directly and only translates `OSError`.
- `ContextService` gains `web_content_service: Optional[WebContentService] = None` as the last constructor keyword and prefers it for the URL scope. The additive shape is what keeps every hand-constructed service green: `test_context_service.py`, `test_context_pdf_embedding.py` and `test_context_service_caching.py` all build the service themselves with seven arguments, and `TestCacheFailureRegression` (the Bug 39 empty-sentinel assertion) therefore survives untouched, to be reversed in Migration per Impact #14.
- The coordinator branch deliberately skips the legacy `""`-to-`None` normalization, because the coordinator signals failure with `None` and never with an empty string. A successful response carrying no extractable text renders as an empty resource instead of the missing marker, which is the slice's stated "Empty body" edge case, and no synthetic sentinel can enter the cache.
- Registration: `IWebContentCache` maps to `WebContentCacheAdapter` in `registries/infrastructure.py` beside `IWebScraper`, and `WebContentService` is registered in `container.py` immediately before `ContextService`, which receives it. Registering the adapter is not optional: `ContextService` now resolves the coordinator, which resolves the port, so an unregistered port breaks every container-resolved assembly test.
- The turn-38 write-risk audit is what made the plain registration safe. No container-resolved assembly passes a URL together with a session root, so nothing writes during the suite: the earliest `test_container_wiring.py` call passes neither, its PDF case calls the scraper directly outside assembly, and the two session-root call sites carry file paths only.
- Red evidence: two of three acceptance tests failed on coordinator-path assertions. The third initially passed against the unwired system because the legacy path keys on `cache_dir`, which that test leaves `None`; the repair added `load_calls == [SESSION_ROOT]`, which the legacy path cannot satisfy, and the rerun failed on exactly that assertion.
- Green evidence: 3 passed in `tests/suites/acceptance/test_web_content_cache_wiring.py`; the unfiltered suite is green at 2606 passed, 5 skipped — the 2603 baseline plus those three tests — with no filesystem-pollution failure.
- Still live after this deliverable: `get_context`'s `cache_dir` parameter, the private `_load_web_cache` / `_save_web_cache` / `_fetch_and_cache_url` helpers, the five-worker fetch pool, the `""` sentinel, and `ActionPorts.web_scraper`, which READ-on-URL and the reviewer preview still reach directly. Migration removes `cache_dir` with its two call sites and migrates the two surfaces; Cleanup removes the helpers, the pool and the sentinel.
- Consequence for Cleanup: once the legacy branch dies, `web_content_service` has no `None` case left, so it becomes a required constructor argument rather than an optional handle. Recorded here so the prune does not leave a permanently nullable seam behind.
- Lint repair: the first commit attempt tripped `PLR0915` (41 > 40) on `_register_orchestration_services`, so the coordinator, `ContextService` and the `IGetContextUseCase` delegate moved into a new `_register_context_assembly_services` helper. `IGetContextUseCase` stays imported in the parent because `PlanningPorts` resolves it, and the registration graph dropped to roughly 36 statements — real headroom rather than a `# noqa` shave.

### Core — Cached fetch coordinator, cap, and tolerated merge
- `fetch_one` lands with the two behaviours Wiring deliberately omitted: an announced cap on the returned value through `cap_extracted_text`, and a `truncate` flag a caller can switch off. The stored body stays verbatim, so a later payload never embeds less than the fetch produced.
- The cap sits after the cache-or-fetch decision rather than inside the fetch, which is what makes a cached hit capped too: a repeat read of a long document costs no round trip and still carries the notice.
- The lookup is a membership test (`url in entries`), not a truthiness check, so a successful response with no extractable text counts as a hit instead of costing a refetch every turn. That is the slice's "Empty body" edge case, and it is why the legacy `""`-to-`None` normalization needed no analogue here.
- `fetch_many` was rewritten around three steps instead of a per-URL loop: one `load_entries`, the misses handed to `_fetch_uncached`, then a single `merge_entries` carrying only the successes. A duplicate URL still resolves once, and a failed URL maps to `None` and is never merged, so the next turn retries it.
- `_fetch_uncached` is the bounded pool: `min(MAX_FETCH_WORKERS, len(misses))` workers so a single miss never allocates five threads, collecting through `as_completed`. `MAX_FETCH_WORKERS = 5` is a module-level code constant rather than a config setting, matching both the legacy pool it replaces and the `ARCHITECTURE.md` allowance for module-level code constants.
- `_merge_entries` catches `WebContentCacheError` alone, logs the session root, and still returns the fetched body. A sibling `OSError` is not tolerated, because that means the cache broke its own contract: the design says losing a completed fetch to a cache write is the worse outcome, not that any write failure is acceptable.
- The broad `except Exception` in `_fetch_verbatim` was kept and made transparent rather than narrowed. The scraper port documents raising on network and HTTP failures, so that is the documented raise surface; what was missing was the record, so the handler now logs the URL with its traceback before rendering the failure as missing. `fetch_one` deliberately bypasses that helper, so a single-URL surface keeps propagating and each caller keeps its existing translation.
- `_read_budget` resolves `read.max_lines` from the optional config handle, falling back to `ReadConfig.max_lines` and rejecting a non-int value the same way, so the budget has one source of truth and no literal enters the coordinator.
- `config_service` stays an optional `None` handle because the component design specifies that shape, with `None` falling back to the schema default. The composition root now injects it, so production never exercises Fallback and Verification step 4's `read.max_lines: 5` takes effect.
- Cache damage tolerance stays Adapter's: neither operation parses JSON, so a corrupt or missing file can only surface as an empty map through `load_entries`.
- Red evidence: 13 tests collected, 13 failed, each a `TypeError` at construction because the coordinator did not accept the config handle. No collection or fixture error, so nothing passed vacuously.
- Green evidence: 13 passed, ruff clean on both touched modules, and the unfiltered suite green at 2619 passed, 5 skipped (the 2606 baseline plus these thirteen) with no filesystem-pollution failure.
- The concurrency proof is a barrier probe rather than a sleep: each scripted fetch parks on a two-party `threading.Barrier`, so the peak in-flight count is the assertion's subject and a sequential coordinator blocks while a concurrent one releases immediately. The timeout only bounds a failing run.
- Still live after this deliverable: the legacy private cache path in `ContextService`, `ActionPorts.web_scraper`, the `WebScraper.get_content` `truncate` flag with the adapter's private `_truncate_content`, and the draft adapter's unlocked direct write. Migration routes the two remaining surfaces and drops the redundant parameter; Adapter hardens the write; Cleanup prunes the flag and the helpers.

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
6. **Preview reuses the cache:**
   Review a plan containing a READ on a URL already fetched this session, then select that action.
   Verify the preview opens the cached body and no new fetch is logged.
7. **Failure retried, not remembered:**
   Keep a READ on an unreachable URL across two turns.
   Verify each turn reports the failure again rather than serving a cached empty document.
