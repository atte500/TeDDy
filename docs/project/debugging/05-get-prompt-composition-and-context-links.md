# Bug: `get-prompt` returns only the agent fragment and `-c` ignores Markdown-link paths
- **Status:** Resolved
- **Milestone:** N/A (ad-hoc)
- **Vertical Slice:** [docs/project/slices/00-35-prompt-composition-and-path-normalization.md](/docs/project/slices/00-35-prompt-composition-and-path-normalization.md)
- **Specs:** [docs/project/specs/interactive-session-workflow.md](/docs/project/specs/interactive-session-workflow.md), [docs/architecture/adapters/inbound/cli.md](/docs/architecture/adapters/inbound/cli.md)

## Symptoms

Two distinct defects on the CLI surface.

**Defect A — `teddy get-prompt <agent>` returns an incomplete prompt.**
- **Expected:** the full composed system prompt the agent actually receives — the `Agent Name: {Agent}` header, the agent-specific XML, and the appended shared MRP base prompt (`<response_format>` … `State Transition Protocol`).
- **Actual:** only the raw agent-specific XML from `.teddy/prompts/<agent>.xml`. The header and MRP block are missing, so pasting the output into a web chat's system-prompt field (the CHOP workflow) yields a model that never emits executable Markdown plans.

Reproduce:
1. In a project with `.teddy/prompts/pathfinder.xml`, run `teddy get-prompt pathfinder`.
2. Observe the output is exactly the file's raw content — no `Agent Name:` header, no `<response_format>` block.

**Defect B — `-c` / `--context` does not accept Markdown-link paths.**
- **Expected:** `-c "[docs/readme.md](docs/readme.md)"` seeds `docs/readme.md` into `session.context`.
- **Actual:** the literal `[docs/readme.md](docs/readme.md)` is written verbatim into `session.context`, so the file is never loaded.

Reproduce:
1. `teddy start -m "hi" -c "[docs/readme.md](docs/readme.md)"`.
2. Inspect `.teddy/sessions/<slug>/session.context` — it contains the raw `[docs/readme.md](docs/readme.md)` line.

## Context & Scope

### Regressing Delta

No recent regression — both are as-built behaviours:
- **Defect A:** `get-prompt` is implemented in `src/teddy_executor/__main__.py:419` (`get_prompt`) via `teddy_executor.prompts.find_prompt_content`, which returns the raw fragment. The only composed-prompt assembly is `PromptManager.fetch_system_prompt` (`src/teddy_executor/core/services/prompt_manager.py:140`), which requires a `turn_path`.
- **Defect B:** `src/teddy_executor/__main__.py:225` splits `-c` on commas + strips; `SessionService._prepare_session_context` (`src/teddy_executor/core/services/session_service.py:86-117`) normalises slashes / `./` / leading `/` but performs no `[label](target)` extraction.

### Environmental Triggers

None — both reproduce on any OS. Defect A needs a `.teddy/prompts/` directory discoverable upward from CWD. Defect B needs a `.teddy/init.context`.

### Ruled Out

- `PromptManager.fetch_system_prompt` composition logic (header + MRP) is correct and covered by `tests/suites/unit/core/services/test_prompt_manager.py` and `tests/suites/acceptance/test_mrp_prompt_assembly.py`.
- `SessionService._extract_resource_path` already parses `[label](target)` for action resource paths — the defect is the `-c` seeding loop not reusing it.

## Diagnostic Analysis

### Causal Model

`teddy get-prompt` resolves the agent prompt through the standalone helper `prompts.find_prompt_content`, which walks upward from CWD for `.teddy/prompts/<name>.*` and returns the file's raw text. It never routes through `PromptManager.fetch_system_prompt`, the only place that prepends `Agent Name: {Agent}` and appends `MRP.xml`. Consequently the CLI emits the fragment only. `fetch_system_prompt` additionally requires a `turn_path`, so `get-prompt` (which has no session/turn) cannot reuse it as-is.

Separately, the `-c` flag is parsed in `__main__.get_start` into a list of trimmed strings and passed as `SessionOptions.additional_context`. `SessionService._prepare_session_context` then normalises each entry (backslash → slash, strip `./`, strip leading `/`) but performs no Markdown-link extraction, so a `[label](target)` entry survives verbatim into `session.context`.

Both legs are now reproduced by failing MREs and their fixes empirically proven in isolation via the Shadow File methodology (Investigation History entries 7, 9 and 10): Defect B by routing each `-c` entry through the link-aware `_extract_resource_path` -- verified by the preservation probe to be a strict superset of the prior inline normalization (all five existing cases preserved) -- and Defect A by composing the prompt through a turn-path-free `compose_system_prompt` seam.

### Discrepancies

- `SessionService` already contains a `[label](target)` regex (`_extract_resource_path`) used for action paths, yet the `-c` seeding path does not use it. (Resolved: `_extract_resource_path` guards action-path context effects; the `-c` seeding loop predates it and was never migrated — a single-sourcing opportunity.)

### Investigation History

1. Hypothesis: `get-prompt` uses the raw fragment path. Observation: `__main__.py:432-434` imports `find_prompt_content` and echoes its result directly. Conclusion: confirmed.
2. Hypothesis: `-c` normalisation lives in `cli_helpers.py`. Observation: grep returned empty; the normaliser is `SessionService._prepare_session_context`. Conclusion: confirmed.
3. Hypothesis: a turn-path-free composed-prompt seam already exists. Observation: composition lives only inside `fetch_system_prompt(agent_name, turn_path)`. Conclusion: a reuse seam is required for `get-prompt`.
4. Hypothesis: `IPromptManager` is a Protocol (adding a method would be free). Observation: it is an ABC (`core/ports/outbound/prompt_manager.py:6`) whose only production implementer is `PromptManager`; all tests use `Mock(spec=...)`/`mock_port`, never a concrete subclass. Conclusion: adding an abstract method is safe.
5. Hypothesis: `PromptManager` requires project initialisation to resolve. Observation: it is registered transiently on the BASE container (`container.py:218-222`) with only `IFileSystemManager` + `IUserInteractor`, both registered by `register_infrastructure`; `session_cli_handlers.py:722` already resolves the port at the boundary without re-init. Conclusion: `container.resolve(IPromptManager)` works in `get-prompt` without `_ensure_project_initialized`.
6. Hypothesis: the composition byte contract is as documented. Observation: `MRP.xml` contains `<response_format>` (line 94) and `State Transition Protocol` (line 5); `canonical_agent_name` is the confirmed header helper. Conclusion: the shadow must reproduce `Agent Name: {canonical}\n\n{content}` then `\n\n{MRP}`, with the `<response_format>` legacy short-circuit preserved.
7. Hypothesis (Defect B sandbox): routing each `-c` entry through the link-aware `_extract_resource_path` fixes the leak while preserving all six existing normalization cases. Observation: `ShadowSessionService` (subclass overriding only `_prepare_session_context`) made MRE B exit 0 with `session.context == ["docs/readme.md"]`. Conclusion: Defect B fix empirically proven in isolation.
8. Hypothesis (Defect A sandbox): a `ShadowPromptManager.compose_system_prompt` seam plus a shadow `get-prompt` command proves composition end-to-end. Observation: the shadow Typer app registered exactly ONE command, so Typer flattened it to the root and consumed `get-prompt` as `prompt_name`, yielding "Got unexpected extra argument(s) (pathfinder)". Conclusion: shadow CLI replicas MUST register ≥2 commands to preserve subcommand semantics; the composition logic was never reached, so this is a harness-shape defect, not a fix defect.
9. Hypothesis (Defect A sandbox, retry): after registering a second placeholder command, the shadow app preserves subcommand semantics and proves composition. Observation: MRE A exited 0 -- output begins with `Agent Name: Pathfinder`, contains `<prompt>Pathfinder</prompt>` and the appended MRP `<response_format>` block, with MRP AFTER the agent content. Conclusion: Defect A fix empirically proven in isolation; both defects now carry verified sandbox fixes (Phase 2 Step 6 complete).
10. Hypothesis (Defect B preservation): routing each `-c` entry through `_extract_resource_path` preserves EVERY pre-existing normalization contract, not only the new link case. Observation: the preservation probe replayed all five existing regression cases (leading-slash strip, `./` strip, backslash normalization, `.hidden` preservation, empty-entry skip) plus the new Markdown-link case through `ShadowSessionService`, exiting 0 with every case `[OK]`. Conclusion: the reuse is a strict superset of the prior inline normalization -- the Defect B fix introduces no regression. This closes the final unverified discrepancy.

### Systemic Audit

**Root Cause Categorization.**
- **Defect A** belongs to the *"two sources of truth for a composed artifact"* category: the composed system prompt has exactly one producer (`PromptManager.fetch_system_prompt`), yet `get-prompt` reached around it to the raw fragment source (`prompts.find_prompt_content`). The fix single-sources composition behind a turn-path-free seam on the port, so any future consumer composes through the same contract.
- **Defect B** belongs to the *"duplicated path-normalization logic"* category: the canonical link-aware normalizer (`SessionService._extract_resource_path`) already existed, but the `-c` seeding loop re-implemented a subset inline and therefore silently lacked `[label](target)` extraction. The fix routes the loop through the canonical helper.

**Categorical Audit — duplicated inline path normalization.** `git grep` for `replace("\\", "/")` and `lstrip("/")` shows the same normalization re-implemented across multiple modules, each a candidate to single-source through a shared pure helper:
- `src/teddy_executor/core/services/session_pruning_service.py:74,97,145`
- `src/teddy_executor/core/services/validation_rules/helpers.py:167,173`
- `src/teddy_executor/core/services/parser_infrastructure.py:114,136`
- `src/teddy_executor/core/services/session_replanner.py:97`
- `src/teddy_executor/adapters/outbound/filesystem_helpers.py:63`
- `src/teddy_executor/adapters/outbound/local_file_system_adapter.py:56,62,137`

`_extract_resource_path` is currently an INSTANCE method on `SessionService`, so the above modules cannot reuse it as-is. The structural follow-up (out of scope for the two defects) is to extract a module-level pure function (e.g. `core/utils/paths.py`) that both `SessionService._extract_resource_path` and these call sites delegate to. Because this is cross-cutting duplication rather than a surgical defect repair, it is recommended for scheduling as a `Refactor` deliverable in the active milestone (Milestone 6: Cross-Cutting Consolidation).

**Impact Audit.**
- `IPromptManager` implementers: `PromptManager(IPromptManager)` (`core/services/prompt_manager.py:22`) is the ONLY production subclass. Every test uses `Mock(spec=IPromptManager)`, `env.mock_port(IPromptManager)`, or `register_mock(container, IPromptManager)` — no concrete subclass exists. Adding a new `@abstractmethod` is therefore non-breaking (additive / Expand-only; no Migrate/Contract phase required).
- `_prepare_session_context` callers: only `SessionService.create_session`. File-local change.
- `get-prompt` command: a single call site in `src/teddy_executor/__main__.py`.

## Solution

**Root cause.** Both defects share one pattern: a canonical single source existed but a consumer bypassed it. For Defect A, the composed system prompt has exactly one producer (`PromptManager.fetch_system_prompt`), yet `get-prompt` reached around it to the raw fragment helper (`prompts.find_prompt_content`); because composition demanded a `turn_path`, the command had no turn-path-free seam to reuse. For Defect B, the canonical link-aware normalizer (`SessionService._extract_resource_path`) already existed, but the `-c` seeding loop in `_prepare_session_context` re-implemented a subset of its normalization inline and therefore silently lacked `[label](target)` extraction.

**Fix (sandbox-proven).** Defect A: extract `_assemble_composed_prompt(agent_name, content)` from `fetch_system_prompt`, expose a turn-path-free `compose_system_prompt(agent_name)` on `IPromptManager`/`PromptManager`, and rewire `get-prompt` to resolve `IPromptManager` from the base container and echo the composed result. Defect B: route each `-c` entry through the existing link-aware `_extract_resource_path` (verified a strict superset of the prior inline normalization). Both fixes were proven in an isolated sandbox before any production edit; implementation is delegated to [Slice 00-35](/docs/project/slices/00-35-prompt-composition-and-path-normalization.md).

**Preventative measures.**
1. Single-source path normalization behind one shared pure module-level helper so every normalizer (`SessionService` plus the six duplicated call sites in the session/pruning/validation/parser/replanner/filesystem layers) delegates to a single function; the `[label](target)` capability and any future normalization rule then propagate everywhere at once instead of drifting silently.
2. Keep composed-prompt assembly behind the `IPromptManager` port seam so no consumer can reach around it to the raw fragment; the CLI now depends on the port, not on `prompts.find_prompt_content`.

### Verified Fix Design (sandbox-proven)

- **Defect A:** extract `_assemble_composed_prompt(agent_name, content)` from `PromptManager.fetch_system_prompt`'s lazy-compose branch; add a public `compose_system_prompt(agent_name)` to the `IPromptManager` port and `PromptManager` that resolves content via `find_prompt_content` and assembles it; rewire the `get-prompt` command to resolve `IPromptManager` from the base container and echo `compose_system_prompt(prompt_name)`.
- **Defect B:** replace the inline per-entry normalization in `SessionService._prepare_session_context` with the existing `_extract_resource_path`, single-sourcing path normalization and gaining `[label](target)` extraction.
