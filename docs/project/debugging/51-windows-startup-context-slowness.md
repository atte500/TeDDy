# Bug: Windows Startup & Per-Turn Latency

- **Status:** Resolved
- **Milestone:** N/A (ad-hoc)
- **Vertical Slice:** [docs/project/slices/00-20-windows-startup-context-latency.md](/docs/project/slices/00-20-windows-startup-context-latency.md)
- **Specs:** [docs/project/specs/plan-execution-context.md](/docs/project/specs/plan-execution-context.md)

## Symptoms

- **Expected:** Comparable `teddy start` readiness time and per-turn `input.md` assembly latency across macOS, Linux, and Windows.
- **Actual:** User reports noticeably longer delay before `teddy start` is ready for the initial prompt, and a longer per-turn delay while context is assembled for `input.md`, on Windows vs macOS.
- **Reproduction:** Identical stage-level probe (`spikes/debug/51-perf-probe.py` via `spikes/debug/probe.sh` and `.github/workflows/debug.yml`) executed locally on macOS and remotely on windows-latest + ubuntu-latest CI (RPP). The probe fails to show comparable timings: Windows cold startup sums to ~15s+ on CLEAN CI before any environmental amplification. (The probe scripts were committed to git history during the RPP runs and retired from the working tree after resolution; `.github/workflows/debug.yml` is retained as a permanent RPP asset.)

## Context & Scope

### Regressing Delta
None. A git history scan found no performance-regressing commit. The root cause is a long-standing platform characteristic (Windows `CreateProcess` cost, ~4x Linux subprocess spawn) amplified by architectural redundancies (unconditional per-start subprocess, double per-turn context gathering, cold-cost clustering on the critical path).

### Environmental Triggers
- Windows OS (spawn-cost amplification: git subprocesses, pre-commit install, python child processes).
- Real-machine amplifiers (secondary, user-confirmed direction): antivirus/Defender real-time scanning of every spawn and file open; hardware delta vs Apple Silicon; larger real projects scaling tree-walk and spawn costs proportionally.
- Config presence: with `.teddy/config.yaml`, the bootstrap preflight triggers the lazy litellm import (3.42s on macOS); without it (CI fixture), the import lands later inside the first planning call.

### Ruled Out
- **NTFS directory traversal:** Windows CI tree generation (94-104ms) is identical to Linux CI (93ms); the gap vs macOS (33ms) is runner hardware, not the filesystem.
- **Warm token counting:** negligible on all platforms (5-14ms).
- **Regression in history:** no perf-regressing commit found.
- **`_check_git_initialized`:** spawns `git init` only when the directory is not already a repo — conditional, not a sibling offender.
- **One-shot `context` command** (session_cli_handlers.py:465): not on the per-turn path.

## Diagnostic Analysis

### Causal Model

**Startup (`teddy start` -> initial prompt), cold, Windows CI (clean):**

1. Interpreter + module imports (typer 0.51s + container module 0.56s): ~1.1s.
2. DI container build (`get_container`): 4.03s (Linux 0.90s; macOS 0.11-1.1s).
3. `_ensure_commit_hooks()` ([session_cli_handlers.py](/src/teddy_executor/adapters/inbound/session_cli_handlers.py):38): unconditionally spawns `pre-commit install -f -t pre-commit -t post-commit` (full Python interpreter + pre-commit framework boot) on EVERY start: **2.96s** on Windows CI vs 0.28s Linux / 0.20s macOS (~10-15x). No skip logic exists; the entire effect is writing two ~20-line hook shims into `.git/hooks/` that embed `INSTALL_PYTHON` + `--hook-type=` args.
4. Config preflight (`validate_config(include_remote=False)`): when `.teddy/config.yaml` exists, triggers the lazy litellm import: 3.42s on macOS; Windows-amplified.
5. Cold tiktoken encoding load (first token count): 2.03s Win / 0.66s Linux / 0.07-0.33s mac.
6. First planning call: `PlanningService.generate_plan` calls `get_context_window` pre-emptively before the LLM completion. Composition: (a) first lazy litellm import if not already imported (Win CI measured 6.99s total for this stage because validate_config short-circuited on CI); (b) for models NOT in `litellm.model_cost`, a synchronous `requests.get("https://openrouter.ai/api/v1/models", timeout=10)` via `OpenRouterMetadataHydrator` — no persistent cache, per-instance memoization only, so every fresh process re-fetches. Registry membership verified: `openrouter/openai/gpt-4o-mini` IS registered (fetch did not fire in probe); README default `openrouter/deepseek/deepseek-v4-flash:nitro` is NOT (fetch fires for default-config users).

**Per-turn (`input.md` assembly):**

7. Context is gathered TWICE per turn: `PlanningService.generate_plan` ([planning_service.py](/src/teddy_executor/core/services/planning_service.py):73) assembles full context (env info + 2 `git status` spawns + repo tree walk + file reads + token counts) and writes `input.md`; then `SessionOrchestrator.execute` ([session_orchestrator.py](/src/teddy_executor/core/services/session_orchestrator.py):264) RE-gathers the same context because the session path passes `project_context=None` (the seam exists end-to-end through the lifecycle manager but is unused in the session path).
8. Per single gathering (warm): Windows 180ms / Linux 60ms / macOS ~80ms. Windows-specific costs: git subprocess spawns ~23.5ms each (Linux ~4ms; macOS ~18.5ms); orchestration overhead. Effective per-turn cost on Windows CI ~400ms vs ~190ms macOS due to the double gather.

**Real-machine multiplier:** Defender/AV scanning of each process spawn and file open, plus hardware and project-size deltas, amplify the measured CI floor.

### Discrepancies

- User-perceived delay exceeded clean-CI partial-path measurements (~80ms/turn, ~2x cold). (Resolved: full-path probe (PASS 3) revealed cold Windows startup sums to ~15s+ on clean CI — pre-commit-install 2.96s, get-container 4.03s, litellm import/hydration ~7s, cold tiktoken 2.03s — plus double context gathering; perception is quantitatively consistent with full-path data.)
- Windows tree walk was expected to be NTFS-slow. (Resolved: Windows and Linux CI trees took identical time; runner hardware dominates the macOS gap.)
- `validate-config-local` measured 0.0s on CI vs 3.42s on macOS. (Resolved: fixture artifact — CI has no `.teddy/config.yaml`, so the preflight short-circuits before the lazy litellm import.)
- `get-context-window` variance: 6.99s Win / 2.84s Linux / 0.12s mac. (Resolved: on CI the stage paid the FIRST lazy litellm import (validate_config short-circuited); on macOS the import was paid earlier by validate_config. Registry membership check proved the network fetch did NOT fire for the probe model (`openrouter/openai/gpt-4o-mini` IS in `model_cost`); the README default model is NOT registered, so the pre-emptive fetch DOES fire for default-config users.)
- Case File 51 vanished from the workspace between turn 24 (EDIT success, 16:15) and turn 31. (Resolved: file was untracked per RPP rule and never committed; lost to workspace cleanup during a parallel session; recreated from preserved data.)

### Investigation History

1. Context gathering + platform check: bug is platform-specific (fails to show comparable timing on Windows) -> pivoted to Remote Probing Protocol.
2. Created MRE probe (PASS 1 cold / PASS 2 warm) and established the macOS local baseline.
3. RPP run 36873737832 (windows-latest + ubuntu-latest): Windows git spawns ~4x Linux (23.5ms vs 5.5ms); tree generation identical Win/Linux (~94ms); warm get-context+tokens 164ms Win / 118ms Linux.
4. History scan: no perf-regressing commit -> long-standing platform characteristic.
5. First RCA presented; user directive: "include everything so also handle_new_session etc".
6. Full stage map of `handle_new_session` bootstrap + `PlanningService.generate_plan` pre-LLM pipeline; probe extended with PASS 3.
7. macOS PASS 3 baseline: `validate-config-local` 3.42s (lazy litellm import) and `pre-commit-install` 0.20s identified as dominant bootstrap stages.
8. RPP attempt #4 (after push-rejection recovery via rebase): full-path Windows numbers captured — cold Win startup ~15s+; double context gathering confirmed in code.
9. Complete RCA presented; user approved compare-and-skip for pre-commit and ruled "keep pre-emptive hydration + persistent registry cache".
10. Code verification: `_ensure_commit_hooks` has zero skip logic; hydration is pre-emptive and synchronous inside `generate_plan`; hook shim anatomy inspected (INSTALL_PYTHON + hook-type args; pre-commit 4.6.0).
11. Systemic Audit: registry membership check (gpt-4o-mini IN, deepseek:nitro NOT); sibling sweep (single `_ensure_commit_hooks` call site; `_check_git_initialized` conditional; `project_context` seam plumbed but unused in session path; `prewarm_imports` lacks tiktoken; single hydrator construction site at registries/infrastructure.py:123-131).

## Solution

*(Finalized after Systemic Audit and user alignment. Implementation is handed off via the linked Vertical Slice.)*

**Root cause:** Long-standing Windows platform cost (process spawning ~4x Linux, `CreateProcess` + AV scanning) multiplied by three architectural redundancies on hot paths: (1) an unconditional `pre-commit install` subprocess executed on every `teddy start` whose entire effect (two hook shims) can be verified with two file reads; (2) double per-turn context gathering because `project_context` is not passed from planning to execution; (3) cold-cost clustering on the startup/first-turn critical path (DI container build, lazy litellm import, cold tiktoken, pre-emptive OpenRouter registry fetch with no persistent cache).

**Fix direction (user-approved):** pre-commit compare-and-skip on `.git/hooks/{pre-commit,post-commit}` shims with fallback to the real install on any mismatch; single context gather per turn via `project_context` wiring (Contract -> Migration -> Cleanup); persistent hydrator registry cache (pre-emptive hydration retained so first-turn telemetry shows real values); extend `prewarm_imports` to cover tiktoken.

**Preventative measures (class-level):** no unverified-effect subprocesses on per-start/per-turn hot paths — every spawn must either check-or-verify its effect or be justified; shared work products (context) must flow through explicit seams instead of being re-derived; one-time heavy costs must be prewarmed or persisted, never re-paid per process.
