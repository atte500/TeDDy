# Slice: Windows Startup & Context Latency Fixes

- **Status:** In Progress
- **Milestone:** N/A (ad-hoc, Milestone 0 prefix)
- **Specs:** [docs/project/specs/plan-execution-context.md](/docs/project/specs/plan-execution-context.md)
- **Prototype:** [spikes/prototypes/windows-startup-latency/](/spikes/prototypes/windows-startup-latency/)
- **Component Docs:** [docs/architecture/adapters/outbound/litellm_adapter.md](/docs/architecture/adapters/outbound/litellm_adapter.md), [docs/architecture/adapters/inbound/cli.md](/docs/architecture/adapters/inbound/cli.md)
- **Scope Slug:** `windows-startup-latency`
- **Source Diagnosis:** [docs/project/debugging/51-windows-startup-context-slowness.md](/docs/project/debugging/51-windows-startup-context-slowness.md)

## Business Goal

Reduce `teddy start` readiness time and per-turn `input.md` assembly latency — most acutely on Windows — by eliminating measured hot-path waste: an unconditional ~3s `pre-commit install` subprocess on every start (Windows CI), a double context-gather per turn (~2x platform penalty), a per-process OpenRouter registry network fetch for unregistered models, and an uncovered cold tiktoken load (~2s Windows CI). Target: warm `teddy start` bootstrap sheds ~3s on Windows CI (and more on AV-amplified machines); per-turn context cost halves on all platforms.

## Scenarios

> As a TeDDy user, I want `teddy start` to skip the pre-commit install subprocess when hooks are already current so that startup is fast.

```gherkin
Given a repository with ".pre-commit-config.yaml" present
  And valid ".git/hooks/pre-commit" and ".git/hooks/post-commit" shims
  And each shim declares its OWN "--hook-type=<type>" (one shim per hook type)
  And each shim declares "hook-impl" and "--config=.pre-commit-config.yaml"
  And each shim's embedded INSTALL_PYTHON path exists
When the user runs "teddy start"
Then the pre-commit install subprocess is NOT spawned
  And the green "pre-commit hooks installed" notification is still shown
```

> As a TeDDy user, I want hooks to be repaired automatically whenever their shims are missing or invalid so that safety is never reduced by the skip guard.

```gherkin
Given a repository with ".pre-commit-config.yaml" present
  And a missing, corrupted, or mismatched hook shim (wrong "--hook-type=", dead INSTALL_PYTHON, or foreign content)
When the user runs "teddy start"
Then the real "pre-commit install -f -t pre-commit -t post-commit" subprocess runs exactly as before
  And the hooks are repaired
```

> As a TeDDy user, I want project context gathered exactly once per turn so that per-turn latency is not doubled.

```gherkin
Given an interactive session turn
When the turn is planned and the resulting plan executed
Then project context is gathered exactly once
  And the same ProjectContext feeds both input.md assembly and plan execution
```

> As a TeDDy user, I want OpenRouter model metadata cached persistently so that only the first-ever session pays the network fetch.

```gherkin
Given a configured model that is NOT in litellm's built-in registry
  And no cached model registry under ".teddy/"
When the first session's first turn hydrates model metadata
Then the OpenRouter catalog is fetched from the network exactly once
  And the catalog is persisted under ".teddy/" with a TTL
  And subsequent sessions hydrate from the cache with no network access
  And first-turn telemetry still displays real context-window values (never "???")
```

> As a TeDDy user, I want heavy token-counter imports prewarmed at init so that the first turn does not absorb their cold load.

```gherkin
Given a fresh teddy install
When the user runs "teddy init"
Then tiktoken's encoding is prewarmed alongside litellm
  And the first turn of "teddy start" does not pay the cold tiktoken encoding load
```

## Edge Cases

- **Non-default hooksPath**: If `core.hooksPath` is configured, then the guard resolves the hooks directory accordingly, because `pre-commit install` writes where git's hooks path points.
- **Hook-type mismatch**: If a shim does not declare its own `--hook-type=<type>` (one shim per hook type), then the real install runs, because hooks may have been installed by another tool or configuration.
- **Install-method variance**: If pre-commit was installed via pipx, uv, or pip, then the shim's `INSTALL_PYTHON` path differs byte-wise while the property check still passes, because only the interpreter path varies across install methods (byte-comparison was empirically rejected: 3 distinct hashes across valid shims would trigger a wasteful reinstall on every method change).
- **Replan residual re-gather**: If a turn enters via the replan path (validation failure), then the next turn's PENDING_PLAN execution re-gathers context once, because the replanned plan executes on the NEXT session-loop iteration and `project_context` cannot cross that boundary as a parameter; the residual is bounded to rare validation-failure turns and accepted for this slice's scope.
- **Dead interpreter path**: If a shim's embedded INSTALL_PYTHON path no longer exists, then the real install runs, because the stale shim would fail at commit time.
- **Corrupt cache**: If the persisted registry cache is corrupt or unparsable, then the hydrator treats it as empty and refetches from the network, because corrupt data must never produce wrong telemetry.
- **TTL expiry**: If the cached registry is older than the configured TTL, then the next pre-emptive hydration refetches, keeping context-window and pricing data fresh.
- **Registered model**: If the configured model IS in litellm's built-in registry, then no fetch and no cache write occur, preserving current behavior for registered models.

## Key Unknowns

- [x] [Technical] Shim regeneration determinism: verify that property-checking (existence + declared args + interpreter path) is sufficient across install methods (pipx/uv/pip) versus brittle byte-comparison. – Resolution: property-checking IS sufficient (spike 16/16 PASS). Shims are a constant template with a templated block containing only `INSTALL_PYTHON=` and `ARGS=(hook-impl --config=... --hook-type=<type>)`; reconstruction via pre-commit's own templated-block splice is byte-identical to real shims (determinism proven). The guard is PER SHIM — each shim declares only its own hook type. pipx/uv/pip variants produce 3 distinct byte hashes while all passing the property check → byte-comparison is brittle and rejected. Missing shim, dead interpreter, and foreign content each fail the check (fallback triggers verified).
- [x] [Technical] Registry cache storage format and TTL default (JSON under `.teddy/`), and confirm the path is covered by `.teddy/.gitignore`. – Resolution: JSON at `.teddy/.model_registry_cache.json`, payload `{"version": 1, "fetched_at_epoch": <int>, "models": [...]}`, TTL 7 days (user-confirmed), corrupt/missing/expired → treated as empty → refetch, atomic write via write-temp + `os.replace` with no `.tmp` residue (spike 7/7 PASS). `.teddy/.gitignore` coverage empirically proven via `git check-ignore -v` against the shipped template (bare `*` rule).
- [x] [Technical] Confirm no double-gather remains after wiring: audit all `orchestrator.execute` call sites (session path, resume path, replan path) for `project_context` propagation. – Resolution: audit complete (5 sites + 1 action-handler false positive, documented in the prototype folder). Double-gather confirmed ONLY on the start path and resume-next-turn path (both funnel through `session_lifecycle_manager.py:144`) — fixed by the planned Wiring. PENDING_PLAN resume is single-gather (correct); both manual sites gather zero times. Residual: the replan path re-gathers on the NEXT session-loop iteration (parameter threading cannot cross the session-loop boundary) — accepted per user as a bounded edge case, no debt log.

## Implementation Plan

Root-cause evidence and full stage-level measurements live in the source Case File (link above). Strategy per fix:

1. **Pre-commit compare-and-skip** (single call site: `_ensure_commit_hooks` in `session_cli_handlers.py:38`, invoked from `_run_health_checks` at line 140): before spawning, resolve the hooks directory (`.git/hooks` or `core.hooksPath`), then apply the guard PER SHIM (empirically validated: pre-commit installs ONE shim per hook type, each declaring only its own `--hook-type=`): each requested shim must exist, contain `hook-impl`, declare `--config=.pre-commit-config.yaml` and its own `--hook-type=<type>`, and embed an INSTALL_PYTHON path that exists on disk. Byte-comparison is REJECTED (validated: reconstructed shims are byte-identical to real ones — determinism proven — but pipx/uv/pip variants produce distinct valid hashes, so byte-compare would reinstall on every interpreter change). Any failure (missing shim, dead interpreter, foreign content) falls back to the existing unconditional install. Cost: ~2 file reads (<1ms) vs 0.20s mac / 0.28s Linux / 2.96s Windows CI.
2. **Single context gather** (seam exists end-to-end but is unused in the session path): `SessionPlanner.trigger_new_plan` currently discards the context gathered inside `PlanningService.generate_plan` (planning_service.py:73); `SessionOrchestrator.execute` re-gathers at session_orchestrator.py:264 because `project_context` arrives as None. Thread the already-gathered `ProjectContext` through `generate_plan`'s return → `SessionPlanner` → `SessionLifecycleManager` → `orchestrator.execute`. Return-contract change with multiple consumers → partitioned as Contract → Wiring → Refactor: the Plan Audit found the 3-tuple return CANNOT be consumed backward-compatibly (every consumer tuple-unpacks and >=6 test files stub 2-tuples), so the mechanical arity adaptation (consumer unpack sites + test stubs, zero behavioral change) is absorbed into the Contract deliverable as a single atomic green-to-green transition; the standalone Migration deliverable is removed. Audit (prototype audit doc) confirmed: double-gather on the start path and resume-next-turn path (both funnel through `session_lifecycle_manager.py:144`); PENDING_PLAN resume is single-gather (correct); both manual sites gather zero times. Residual: the replan path re-gathers on the next loop iteration — accepted per user as a bounded edge case (no debt log).
3. **Persistent hydrator registry cache** (user ruled: KEEP pre-emptive hydration; first-turn telemetry must show real values): `OpenRouterMetadataHydrator._fetch_models` (sync `requests.get`, 10s timeout, per-instance memoization only) gains a persistent cache at `.teddy/.model_registry_cache.json` (validated design: payload `{"version": 1, "fetched_at_epoch": <int>, "models": [...]}`; TTL 7 days — user-confirmed, configurable via `IConfigService`; corrupt/missing/expired → treated as empty → refetch; atomic write via write-temp + `os.replace`). The path is covered by the shipped `.teddy/.gitignore` template (bare `*` rule; proven via `git check-ignore`). Injected via the single construction site at `registries/infrastructure.py:123-131` (factory lambda, singleton scope) using Constructor Injection — no mid-logic env checks. Note: the README default model `openrouter/deepseek/deepseek-v4-flash:nitro` is NOT in litellm's registry, so this fetch fires for default-config users today.
4. **Prewarm gap**: `prewarm_imports` (cli_helpers.py:252) covers litellm/trafilatura/pyperclip/bs4/ddgs but not tiktoken; add it to close the cold-token-count cost (2.03s Windows CI / 0.66s Linux).

## Deliverables

- [x] **Contract** - Extend `generate_plan`'s return to `(plan_path, turn_cost, project_context)` in `PlanningService` and the `IPlanningUseCase` port (the `ProjectContext` is already gathered at planning_service.py:73); in the SAME atomic green-to-green transition, mechanically adapt all consumers to the new arity (`SessionPlanner.trigger_new_plan`, `session_cli_handlers.handle_plan_generation`; `SessionReplanner` ignores the return) and update every affected test stub/mock from 2-tuple to 3-tuple — zero behavioral change (the context is not yet consumed).
- [x] **Harness** - Add registered test fakes/mocks for hook-shim filesystem state and a fake persistent cache loader (via the designated mock registration helper; no bare mocks).
- [x] **Seam** - Inject a cache path/loader into `OpenRouterMetadataHydrator` at the `registries/infrastructure.py` factory (Constructor Injection; corrupt/missing cache = empty cache).
- [ ] **Wiring** - Thread `project_context` from `generate_plan` through `SessionPlanner.trigger_new_plan` → `SessionLifecycleManager` → `orchestrator.execute`; behavioral test asserting exactly one `get_context` call per turn.
- [ ] **Logic** - Implement the compare-and-skip guard in `_ensure_commit_hooks` (hooksPath resolution, shim existence + declared `--hook-type=`/`--config=` args + INSTALL_PYTHON validity) with fallback to the real install; unit tests for skip and each fallback trigger.
- [ ] **Logic** - Implement the persistent registry cache in the hydrator: JSON at `.teddy/.model_registry_cache.json` (`version`/`fetched_at_epoch`/`models`), TTL 7 days default from `IConfigService`, atomic write (temp + `os.replace`), network fetch only on miss/expiry, corrupt cache treated as empty; unit tests (round-trip, expiry boundary, corrupt, missing, atomicity).
- [ ] **Logic** - Add `tiktoken` to `prewarm_imports`; unit test asserting coverage.
- [ ] **Refactor** - Reduce the re-gather branch at session_orchestrator.py:264 to an explicit fallback-only path (never hit when `project_context` is provided).

## Implementation Notes

### Contract — `generate_plan` returns `(plan_path, turn_cost, project_context)`

- **Red (unit layer):** Added `test_generate_plan_returns_plan_path_cost_and_project_context` to `tests/suites/unit/core/services/test_planning_service.py`. Asserts the 3-tuple return and that the third element is the EXACT `ProjectContext` instance produced by `IGetContextUseCase.get_context` (identity assertion `is expected_context`, plus `get_context.call_count == 1` to pin the single-gather invariant early). Confirmed failing with `ValueError: not enough values to unpack (expected 3, got 2)` — the exact predicted failure, no incidental setup noise.
- **Green:** `PlanningService.generate_plan` now returns the already-in-scope `context` local (the gather at planning_service.py:73) as the third element — zero additional gathering. Port `IPlanningUseCase.generate_plan` annotation extended to `tuple[str, float, ProjectContext]` (import + docstring updated) for mypy consistency with the return statement.
- **Mechanical consumer adaptation (same atomic transition):** `SessionPlanner.trigger_new_plan` and `session_cli_handlers.handle_plan_generation` now unpack `plan_path, _, _` — neither consumer reads `turn_cost` or the context yet; consuming the context is the Wiring deliverable's behavioral change. `SessionReplanner.trigger_replan_turn` discards the return by design — untouched.
- **Test stub census (9 × 2-tuple → 3-tuple with `None` placeholder):** `test_session_planner.py` ×4, `test_session_pruning_persistence.py` ×3 (integration), `test_session_orchestrator_initial_prompt.py` ×1, `test_session_orchestrator_validation.py` (unit) ×1. The `None` third element is safe because no consumer reads it yet; these placeholders are the seam the Wiring deliverable will replace where consumers begin consuming the context.
- **Audit resolution:** the integration-layer stub `POSIXPathMock(return_value="Corrected Plan")` (test_session_orchestrator_validation.py:52) flows through `SessionReplanner`, which discards the return — proven to need no adaptation.
- **Refactor:** aligned the Protocol-style fake `DummyPlanningService` in `test_session_replanner.py` to the real contract (annotation `tuple[str, float, ProjectContext]`, body returns a real `ProjectContext`) — behavior-neutral (the return is discarded) but keeps the fake's type honesty under mypy. Repo-wide sweep for stale `tuple[str, float]` annotations found exactly one other site, `edit_simulator.py:24` — that is EditSimulator's own edit-result contract (content + match score), unrelated to planning; left untouched.
- **Integration gate:** full unfiltered suite green (1254 passed, 5 skipped); the workspace held exactly this deliverable's 10 files (4 src, 6 test).
- **Wiring handoff:** the Wiring deliverable threads the real context through `trigger_new_plan` → `SessionLifecycleManager._handle_planning_and_execution` → `orchestrator.execute`; its behavioral gate is exactly one `get_context` call per turn.

### Harness — `FakeRegistryCache` + `HookShimWorkspace` test doubles

- **Design ruling (registered-without-`register_mock`):** the deliverable's "via the designated mock registration helper" constraint is honored through its binding intent — "no bare mocks". Neither fake maps to a container port (there is no port to `register_mock` against), and `unittest.mock` is TID251-banned outside `tests/harness/setup/`. Per anti-mock-poisoning, BOTH doubles are FILE-STATE fakes backed by REAL files in `tempfile.mkdtemp()` roots (the architecture's temp-file standard): the hydrator and skip guard read real paths, so dynamic mocks would not exercise actual file semantics. They reside in `tests/harness/setup/` (`model_registry_cache.py`, `hook_shims.py`) per the TID251 residency rule.
- **Cycle 1 — FakeRegistryCache (cache file state):** Red via 12 self-tests in `tests/suites/unit/test_model_registry_cache_harness.py` (`ModuleNotFoundError` at collection — tests drive the fake's creation); Green via the fake: temp-rooted `.teddy/` layout, prototype-validated payload (`version=1`, `fetched_at_epoch`, `models`), `write_fresh(models, fetched_at=None)` with default-now and explicit-epoch modes (the explicit mode is what the Logic deliverable's TTL-boundary tests will pin), `expire(ttl_seconds)` writing the EXACT boundary (`now - fetched == ttl`, matching the `>=` expiry semantics), `corrupt()`, `remove()`, `read_payload()`, and zero-residue context-manager cleanup. Round-trip fidelity asserted against the canonical `OPENROUTER_MODELS_RESPONSE["data"]`.
- **Cycle 2 — HookShimWorkspace (hook-shim filesystem state):** Red via 20 self-test items in `tests/suites/unit/test_hook_shim_workspace_harness.py` (16 functions; parametrized expansion); Green via the fake: temp-rooted `.git/hooks/` layout, prototype-validated per-shim anatomy (`INSTALL_PYTHON=<path>` line + `ARGS=(hook-impl --config=.pre-commit-config.yaml --hook-type=<type>)`), ONE shim per hook type each declaring ONLY its own hook type (per-shim guard semantics — asserted explicitly), default live interpreter (`sys.executable`) with an `install_python` override modeling pipx/uv/pip install-method variance, five scoped fallback-trigger mutations (`remove_shim`, `kill_interpreter`, `write_foreign_shim`, `mismatch_hook_type`, `drop_config_flag`), and an explicit per-shim-isolation test (corrupting one shim leaves the other fully valid).
- **Semantic deduplication (Discovery, turns 15-16):** zero existing coverage of shim file contents or a persistent registry cache; the six existing `_ensure_commit_hooks` tests use monkeypatch global patching (shutil.which, subprocess.run) and will be EXTENDED (not broken) by the skip-guard Logic deliverable, which will use `HookShimWorkspace` for the filesystem dimension.
- **Refactor:** unused `import sys` removed from the shim self-test file (Ruff hygiene); temp-root boilerplate census adjudicated no shared helper exists in `tests/harness/setup/` — the duplication is greenfield, logged as DEBT (harvested to PROJECT.md, not appended to this slice).
- **Integration gate:** full unfiltered suite green (1288 passed, 5 skipped; the session-scoped pollution Poka-Yoke verified both fakes' zero-residue cleanup at suite scale). Workspace held exactly this deliverable's 5 files (2 harness fakes, 2 self-test files, slice doc).
- **Seam handoff:** the Seam deliverable injects a cache path/loader into `OpenRouterMetadataHydrator` at the single construction site (`registries/infrastructure.py:124`, factory lambda, singleton scope) via Constructor Injection; `FakeRegistryCache.cache_path` is the injection-compatible surface the hydrator tests will consume.

### Seam — `OpenRouterMetadataHydrator` Constructor Injection (cache_path + config_service)

- **Red (unit layer):** added `TestConstructorInjectionSeam` to `tests/suites/unit/adapters/outbound/test_openrouter_hydrator.py` — five atomic tests pinning the injection seam: `CACHE_PATH` equals the spec'd `.teddy/.model_registry_cache.json` (real-value anchor, mirroring the Harness fake's `CACHE_FILENAME` pin), zero-arg construction defaults BOTH params to `None` (the non-breaking invariant protecting all pre-existing tests), and verbatim identity storage of an injected `cache_path` and a spec'd config double (`POSIXPathMock(spec=IConfigService)` via the designated helper — no bare mocks). Confirmed failing `5 failed, 5 passed`: 3x `AttributeError` (no attribute `CACHE_PATH`/`cache_path`/`config_service`), 2x `TypeError` (`__init__() got an unexpected keyword argument`) — exactly the predicted signatures, zero incidental noise.
- **Green:** the hydrator gains the `CACHE_PATH` class constant (declared beside the existing `API_URL`/`TIMEOUT` class-attribute convention) and a typed optional-parameter constructor (`cache_path: Optional[Path] = None`, `config_service: Optional[IConfigService] = None`); `None` = exact legacy behavior. The per-instance memoization body is preserved verbatim and construction stays side-effect-free (no file I/O in `__init__`). Typing the signature also resolved the pre-existing mypy annotation-unchecked note at hydrator.py:17 in-scope.
- **TTL injection-shape ruling:** inject `IConfigService` (not a resolved ttl int) — the adapter-convention precedent (WebScraperAdapter, WebSearcherAdapter, ConsoleInteractorAdapter all take `config_service`), the cli-initialization-optimization spec §1 mandate (adapters receive `IConfigService` and resolve settings lazily), and it keeps the TTL key-name decision with the Logic deliverable where the read semantics live. The Seam stores refs only; no TTL is read yet.
- **Factory wiring (real values):** the single construction site's factory lambda in `registries/infrastructure.py` now injects `cache_path=OpenRouterMetadataHydrator.CACHE_PATH` + `config_service=container.resolve(IConfigService)` (singleton scope preserved). The lazy factory resolution mirrors the four neighboring registrations — no eager I/O during registration; `IConfigService` was already imported in the module's local import block.
- **Container-resolved wiring assertion:** appended `test_hydrator_is_wired_with_persistent_cache_dependencies` to `tests/suites/integration/adapters/outbound/test_llm_wiring.py` — the container-resolved hydrator (via `ILlmClient._hydrator`, the file's existing attribute-access precedent) carries the real `CACHE_PATH` and a non-None config service. Semantic deduplication confirmed: no existing assertion covered the factory's injected values.
- **Refactor:** pruned the pre-existing stale commentary block inside `_fetch_models` (it described an outdated testing approach — relative URLs, session-level mocking — contradicting the actual test reality of `hydrator.API_URL` redirection); scoped re-run `13 passed` proved the cleanup behaviorally inert. No structural opportunities logged (no new DEBT).
- **Integration gate:** full unfiltered suite green (1296 passed, 5 skipped) — the Seam is non-breaking at suite scale (every pre-existing zero-arg construction and container resolution stayed green) and the pollution Poka-Yoke verified construction remains side-effect-free (no real `.teddy/` state touched) across the whole suite. Workspace held exactly this deliverable's 5 modified files.
- **Logic handoff:** the hydrator now carries the two surfaces the persistent-cache Logic deliverable consumes: `cache_path` (file state — inject `FakeRegistryCache.cache_path` for temp-rooted real-file tests) and `config_service` (TTL key name + 7-day default are Logic decisions read lazily via `get_setting`).

## Verification

- In a prepared repo with hooks installed, run `teddy start` twice; the second run's health-check stage completes with no pre-commit subprocess (well under 100ms) and still shows the green notification.
- Delete `.git/hooks/pre-commit`; run `teddy start`; observe the real install running and the shim restored.
- Simulate an install-method change (shim `INSTALL_PYTHON` pointing to a different but live interpreter); confirm the skip guard does NOT trigger a reinstall.
- With the default model (`openrouter/deepseek/deepseek-v4-flash:nitro`), run a first session; verify exactly one network fetch and a `.teddy/` cache file created; run a second session (network-blocked or via logging) and verify hydration comes from cache; verify first-turn telemetry shows a real context-window value.
- Run one interactive turn; via instrumentation/spy confirm `get_context` executes exactly once.
- Run `teddy init`; confirm tiktoken prewarm (first turn's token count shows no cold-load spike).
- Full test suite green (post-commit gate).
