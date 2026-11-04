# Bug: plan.max_lines Ignored Because ContextService Loses Its Config Service
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
Expected: with `plan.max_lines: 5` in `.teddy/config.yaml`, every `plan.md` embedded in a session turn's `input.md` is head-truncated to five lines and carries a `[Showing first 5 of N lines.]` marker, while the on-disk plan stays full.

Actual: session `input.md` embeds complete plan bodies. The literal marker `[Showing first 5 of` appears zero times across every `input.md` of the reported session (`.teddy/sessions/20261104_125849-done-test-set-plan-max-lines-still/01..05/input.md`), and the Session History section reproduces earlier turns' plans in full.

Minimal reproduction: set `plan.max_lines` below the length of any plan, run a session for at least two turns, then inspect `.teddy/sessions/<slug>/<NN>/input.md`.

## Context & Scope
### Regressing Delta
Two changes 229 days apart that were never reconciled in `src/teddy_executor/container.py`:

- `f9cf68f28` (2026-03-16) introduced `container.register(IGetContextUseCase, ContextService, scope=punq.Scope.transient)`, the interface registration that consumers actually resolve. punq auto-resolves the constructor, and `ContextService.__init__` declares `config_service: Optional[IConfigService] = None`, so the port was built without a config handle from the day it shipped.
- `4192a0677` (2026-11-03) added `config_service=container.resolve(IConfigService)` to the concrete `ContextService` factory at lines 223-233 when the `plan.max_lines` cap was introduced. The interface registration was not updated, so the injected config service never reached any consumer that resolves `IGetContextUseCase`.

### Environmental Triggers
- `.teddy/config.yaml` carrying `plan.max_lines` below the length of the plans in the session. With the effective fallback of 5000, no realistic session plan reaches the cap, so the setting appears to be inert rather than misapplied.
- Session turns only, because `plan.md` files enter the payload through the session and turn context manifests.
- The cap applies to plan files alone; other resources embed verbatim, so their full content is expected.

### Ruled Out
- `YamlConfigAdapter` resolution: constructing the adapter against the real configuration yields `plan.max_lines = 5` (raw block `{'max_lines': 5}`, typed view `5`, schema default `5000`).
- `ContextService` cap logic: `_cap_plan_contents` head-truncates every `file_contents` entry whose path ends with `plan.md`, and the integration test `tests/suites/integration/core/services/test_context_plan_cap.py` passes with an injected config service.
- Key-shape mismatch: manifest paths are passed verbatim to `read_files_in_vault`, which returns them as keys unchanged, and those keys end with `plan.md`.
- Renderer bypass: `_format_session_history` and `_format_workspace_contents` both read the same `file_contents` map that `_cap_plan_contents` mutates; no disk re-read occurs during formatting.

## Diagnostic Analysis
### Causal Model
The composition root registers `ContextService` twice. The first registration supplies a factory that injects `file_system_manager`, `repo_tree_generator`, `environment_inspector`, `llm_client`, `web_scraper`, and `config_service`. The second registers the inbound port `IGetContextUseCase` against the bare `ContextService` class. punq builds that second form through automatic constructor resolution, cannot resolve the `Optional[IConfigService]` annotation, and substitutes the parameter default `None`. With no config service, `_resolve_plan_max_lines` short-circuits to `DEFAULT_APP_CONFIG.plan.max_lines` (5000), so `_cap_plan_contents` truncates nothing for any realistic plan and the configured `plan.max_lines` never takes effect. The integration test passes because it constructs `ContextService` directly with an injected config service, bypassing the composition root.

### Discrepancies
- [x] Configured `plan.max_lines: 5` has no effect on session `input.md`, while the same value resolves correctly through `YamlConfigAdapter` (Resolved: the adapter is correct; the container-built context service never receives it).
- [x] The cap logic is covered by a passing integration test, yet no real payload ever carries the truncation marker (Resolved: the test constructs `ContextService` directly with an injected config service and therefore bypasses the composition root).
- [x] Discrepancy between expected and observed behavior (Resolved: the container-built `ContextService` receives no config service, so the cap falls back to 5000).

### Investigation History
1. Investigated whether `plan.max_lines` is a real consumed setting by grepping the repository; observed `_cap_plan_contents` and `_resolve_plan_max_lines` in `ContextService` plus schema and config entries, which confirmed the setting exists and is consumed.
2. Investigated whether the cap and the renderer share state by reading `_format_content`, `_format_workspace_contents`, and `_format_session_history`; observed both render from the same `file_contents` map that `_cap_plan_contents` mutates, which ruled out a render-time re-read.
3. Investigated whether the cap predicate misses production paths by reading `_cap_plan_contents` and `_resolve_files_to_paths`; observed the predicate is `path.endswith("plan.md")` over manifest paths passed verbatim, which ruled out a key-shape mismatch.
4. Investigated whether `input.md` actually contains truncation by counting `Showing first` per payload; observed nonzero counts, but also observed the same phrase inside the session's own plan prose, which invalidated that count.
5. Investigated the truncation marker literally and the real Session History body; observed zero occurrences of `[Showing first 5 of` in every `input.md` while turn plans embed in full, which confirmed capping never fires in production.
6. Investigated config resolution by building `YamlConfigAdapter` against the real workspace; observed `plan.max_lines -> 5`, which ruled out the adapter.
7. Investigated the composition root by reading the registrations and resolving `IGetContextUseCase` from the real container; observed `_config_service -> None` and `_resolve_plan_max_lines() -> 5000` while `IConfigService` resolves to `YamlConfigAdapter`, which confirmed the duplicate-registration root cause.
8. Investigated the configuration source by reading `registries/infrastructure.py`; observed `IConfigService -> YamlConfigAdapter()` reading `.teddy/config.yaml` from the process CWD, which made a self-contained temp-workspace reproduction possible without touching the live config.
9. Investigated the defect end-to-end by building `create_container()` inside a temp CWD carrying `plan.max_lines: 5` and a ten-line `plan.md`; observed `adapter plan cap -> 5`, `_config_service -> None`, `_resolve_plan_max_lines -> 5000`, no truncation marker, and the full plan embedded, which reproduced the symptom under controlled configuration.
10. Investigated the proposed fix by copying `container.py` to `spikes/debug/plan-max-lines-ignored/replica_container.py` and changing only the interface registration to delegate to the concrete factory; observed production `NOT TRUNCATED` (exit 1) versus replica `TRUNCATED` (exit 0: effective cap 5, marker present, tail absent) from identical inputs, which proved the delegation in isolation.
11. Investigated the fix in production by applying the delegation to `src/teddy_executor/container.py` and re-running the MRE; observed `service has config -> True`, `effective plan cap -> 5`, marker present, tail absent (`TRUNCATED`), which confirmed the fix in `src/`. Added two regressions to `test_container_wiring.py` (the port carries an `IConfigService`; the container-built service caps a ten-line `plan.md` at `plan.max_lines: 5`) and confirmed `make test` green with 2201 passed and 5 skipped.

## Solution
### Root Cause
Verified and directly fixed in `src/`. The composition root registered `ContextService` twice: a concrete factory that injects `config_service`, then an interface registration against the bare class. punq auto-resolved the constructor for the interface registration and substituted the parameter default `None`, so `_resolve_plan_max_lines` fell back to the schema default (5000) and the configured `plan.max_lines` never applied. The fix is a small self-contained change to one production file plus its matching test file: the interface registration now delegates to the concrete registration, so the port inherits the injected config service.

Preserved verification artifacts:
- `spikes/debug/plan-max-lines-ignored/77-plan-max-lines-ignored-mre.py`: builds the real composition root in a temp workspace with `plan.max_lines: 5` and reports whether the embedded plan is truncated. Invoke with `production` or `replica`.
- `spikes/debug/plan-max-lines-ignored/replica_container.py`: faithful copy of the pre-fix `container.py` with the single delegation change, used to prove the fix in isolation before touching production code.

### Affected Components
- `src/teddy_executor/container.py` (changed): the `IGetContextUseCase` registration delegates via `factory=lambda: container.resolve(ContextService)`, so the inbound port inherits the config service.
- `tests/suites/integration/core/services/test_container_wiring.py` (changed): two new regressions assert the port carries an `IConfigService` and that the container-built service caps a ten-line `plan.md` at `plan.max_lines: 5` with the truncation marker.
- `src/teddy_executor/core/services/context_service.py` (unchanged): still consumes the optional config handle through `_resolve_plan_max_lines`; the optional parameter remains part of the contract.
- `SessionOrchestrator` and `PlanningPorts` factories plus the session CLI handler (unchanged): they resolve `IGetContextUseCase` and now receive a context service with its config handle; only plan-file content changes, which is the intended fix.
- `tests/suites/integration/core/services/test_context_plan_cap.py` (unchanged): remains valid and green; it constructs the service directly with an injected config service.
- `tests/suites/unit/core/services/test_context_service.py` and `test_context_git_status_parsing.py` (unchanged): register the pair on their own containers with mocked ports and are unaffected because `ContextService` still accepts `config_service=None`.
