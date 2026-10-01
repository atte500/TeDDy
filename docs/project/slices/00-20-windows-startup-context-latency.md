# Slice: Windows Startup & Context Latency Fixes

- **Status:** Planned
- **Milestone:** N/A (ad-hoc, Milestone 0 prefix)
- **Specs:** [docs/project/specs/plan-execution-context.md](/docs/project/specs/plan-execution-context.md)
- **Prototype:** N/A
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
  And each shim declares the requested "--hook-type=" values and "--config=.pre-commit-config.yaml"
  And the shim's embedded INSTALL_PYTHON path exists
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
- **Hook-type mismatch**: If a shim declares different `--hook-type=` values than requested, then the real install runs, because hooks may have been installed by another tool or configuration.
- **Dead interpreter path**: If a shim's embedded INSTALL_PYTHON path no longer exists, then the real install runs, because the stale shim would fail at commit time.
- **Corrupt cache**: If the persisted registry cache is corrupt or unparsable, then the hydrator treats it as empty and refetches from the network, because corrupt data must never produce wrong telemetry.
- **TTL expiry**: If the cached registry is older than the configured TTL, then the next pre-emptive hydration refetches, keeping context-window and pricing data fresh.
- **Registered model**: If the configured model IS in litellm's built-in registry, then no fetch and no cache write occur, preserving current behavior for registered models.

## Key Unknowns

- [ ] [Technical] Shim regeneration determinism: verify that property-checking (existence + declared args + interpreter path) is sufficient across install methods (pipx/uv/pip) versus brittle byte-comparison.
- [ ] [Technical] Registry cache storage format and TTL default (JSON under `.teddy/`), and confirm the path is covered by `.teddy/.gitignore`.
- [ ] [Technical] Confirm no double-gather remains after wiring: audit all `orchestrator.execute` call sites (session path, resume path, replan path) for `project_context` propagation.

## Implementation Plan

Root-cause evidence and full stage-level measurements live in the source Case File (link above). Strategy per fix:

1. **Pre-commit compare-and-skip** (single call site: `_ensure_commit_hooks` in `session_cli_handlers.py:38`, invoked from `_run_health_checks` at line 140): before spawning, resolve the hooks directory (`.git/hooks` or `core.hooksPath`), verify both shims exist and declare the requested `--hook-type=` values and `--config=.pre-commit-config.yaml`, and verify the embedded INSTALL_PYTHON path exists. Any failure falls back to the existing unconditional install. Cost: ~2 file reads (<1ms) vs 0.20s mac / 0.28s Linux / 2.96s Windows CI.
2. **Single context gather** (seam exists end-to-end but is unused in the session path): `SessionPlanner.trigger_new_plan` currently discards the context gathered inside `PlanningService.generate_plan` (planning_service.py:73); `SessionOrchestrator.execute` re-gathers at session_orchestrator.py:264 because `project_context` arrives as None. Thread the already-gathered `ProjectContext` through `generate_plan`'s return → `SessionPlanner` → `SessionLifecycleManager` → `orchestrator.execute`. Return-contract change with multiple consumers → partitioned as Contract → Migration → Cleanup.
3. **Persistent hydrator registry cache** (user ruled: KEEP pre-emptive hydration; first-turn telemetry must show real values): `OpenRouterMetadataHydrator._fetch_models` (sync `requests.get`, 10s timeout, per-instance memoization only) gains a persistent cache under `.teddy/` with a TTL. Injected via the single construction site at `registries/infrastructure.py:123-131` (factory lambda) using Constructor Injection — no mid-logic env checks. Note: the README default model `openrouter/deepseek/deepseek-v4-flash:nitro` is NOT in litellm's registry, so this fetch fires for default-config users today.
4. **Prewarm gap**: `prewarm_imports` (cli_helpers.py:252) covers litellm/trafilatura/pyperclip/bs4/ddgs but not tiktoken; add it to close the cold-token-count cost (2.03s Windows CI / 0.66s Linux).

## Deliverables

- [ ] **Contract** - Extend the planning result so the already-gathered `ProjectContext` is returned by `generate_plan` (additive to the `(plan_path, turn_cost)` return; keep backward-compatible consumption possible during migration).
- [ ] **Harness** - Add registered test fakes/mocks for hook-shim filesystem state and a fake persistent cache loader (via the designated mock registration helper; no bare mocks).
- [ ] **Seam** - Inject a cache path/loader into `OpenRouterMetadataHydrator` at the `registries/infrastructure.py` factory (Constructor Injection; corrupt/missing cache = empty cache).
- [ ] **Wiring** - Thread `project_context` from `generate_plan` through `SessionPlanner.trigger_new_plan` → `SessionLifecycleManager` → `orchestrator.execute`; behavioral test asserting exactly one `get_context` call per turn.
- [ ] **Logic** - Implement the compare-and-skip guard in `_ensure_commit_hooks` (hooksPath resolution, shim existence + declared `--hook-type=`/`--config=` args + INSTALL_PYTHON validity) with fallback to the real install; unit tests for skip and each fallback trigger.
- [ ] **Logic** - Implement the persistent registry cache with TTL in the hydrator (network fetch only on miss/expiry; corrupt cache treated as empty); unit tests.
- [ ] **Logic** - Add `tiktoken` to `prewarm_imports`; unit test asserting coverage.
- [ ] **Migration** - Update all `generate_plan` consumers (`SessionPlanner`, lifecycle-manager paths, affected tests) to the extended return contract.
- [ ] **Refactor** - Reduce the re-gather branch at session_orchestrator.py:264 to an explicit fallback-only path (never hit when `project_context` is provided).

## Implementation Notes

*(Filled by the Developer during implementation.)*

## Verification

- In a prepared repo with hooks installed, run `teddy start` twice; the second run's health-check stage completes with no pre-commit subprocess (well under 100ms) and still shows the green notification.
- Delete `.git/hooks/pre-commit`; run `teddy start`; observe the real install running and the shim restored.
- With the default model (`openrouter/deepseek/deepseek-v4-flash:nitro`), run a first session; verify exactly one network fetch and a `.teddy/` cache file created; run a second session (network-blocked or via logging) and verify hydration comes from cache; verify first-turn telemetry shows a real context-window value.
- Run one interactive turn; via instrumentation/spy confirm `get_context` executes exactly once.
- Run `teddy init`; confirm tiktoken prewarm (first turn's token count shows no cold-load spike).
- Full test suite green (post-commit gate).
