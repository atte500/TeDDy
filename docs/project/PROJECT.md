# Project: TeDDy

## Product Vision

TeDDy's mission is to apply the **UNIX philosophy** to AI development and create a **Git-like workflow** to embed the entire AI collaboration process directly into the file system.

- **Markdown Files as Interface:** The interface *is* the file system. AI collaboration lives exclusively in plain Markdown files in the local directory, managed with standard developer tools.
- **Local-First & Data Ownership:** No cloud lock-in. Total control over privacy and data. The complete workflow and context history resides on the local machine in a portable, open format.
- **Stateless & Transparent:** Context goes in as a file, results come out as a file. Every turn is completely deterministic, auditable, and hackable.
- **Human-Centric Workflow:** Action plans are reviewed and approved interactively before execution. A suite of specialized AI personas (Pathfinder, Architect, Developer, Debugger) tackle distinct phases of the software lifecycle using disciplined, proven workflows.

## Guiding Principles

1.  **Jidoka (Autonomation):** *Stop the line immediately when a defect is found.* We make errors obvious so they can be fixed, rather than masking them. Test-Driven Development (TDD) is our primary implementation of Jidoka, preventing flawed code from ever being integrated.
2.  **Poka-Yoke (Mistake-Proofing):** *Design processes so errors can't be made in the first place.* Contract-First Design is our Poka-Yoke. By defining clear "seams" and contracts between all parts of the system—starting with the user—we mistake-proof the architecture.
3.  **The UNIX Philosophy (Small, Sharp Tools):** *Build small, independent components that do one thing well and compose them to handle complexity.* This principle is the foundation of our architecture and development workflow. Each component is a "small, sharp tool" with a single responsibility, communicating through simple, well-defined contracts (Ports).

## Workflow Standards

This section defines the conventions for our project management artifacts.

- **Artifact Lifecycle:** Work flows from `Spec` -> `Milestone` -> `Slice`.
- **Numbering:** Artifacts are numbered sequentially using an `MM-NN-name.md` format, where `MM` represents the target Milestone number and `NN` represents the specific Slice or Case File number. For ad-hoc tasks not tied to an active milestone, `00` is used as the Milestone prefix (e.g., `00-01-ad-hoc-feature.md`). Ad-hoc slices are NOT tracked in Milestone documents or the Roadmap.
- **Archiving Policy:** Once a feature slice or milestone is fully implemented and merged, its active planning artifacts can be deleted. The Git history serves as the official, permanent archive.

## Roadmap

### Milestone 1: Structural Protocol & Parser [COMPLETED]
- **Core Goal:** Move from action-based communication (`INVOKE`, `RETURN`, `PROMPT`) to the structural `## Message` protocol.
- **Requirements:**
    - **CLI Polish:** Update `start` command to support `-a/--agent`, `-m/--message`, and `-c/--context` flags for fluid handoffs.
    - **Parser Cleanup:** Remove legacy `PROMPT`, `INVOKE`, and `RETURN` actions from `MarkdownPlanParser` and `PlanValidator`.
    - **Orchestrator:** Ensure `ExecutionOrchestrator` handles "Message Turns" (no actions) without side-effects.
    - **Prompt Migration:** Update all system prompts (`pathfinder`, `architect`, `developer`, `debugger`, `assistant`, `prototyper`) to use `## Message` for all communication and handoffs.

### Milestone 2: Stability & Infrastructure [COMPLETED]
- **Core Goal:** Hardening the system against external failures, ensuring safety limits, and improving context/session management.
- **Requirements:**
    - **LLM Resilience:** Implement retry logic (3 attempts) for SSL and OpenRouter timeout errors (Reproduce via: `SSLV3_ALERT_BAD_RECORD_MAC`).
    - **Web Scraper (403 Bypassing):** Attempt to bypass 403 Forbidden errors via User-Agent rotation and common headers (Reproduce via: `https://www.pnas.org/doi/10.1073/pnas.2416294121`).
    - **GitHub Compatibility:** Fix content extraction for `raw.githubusercontent.com` links that currently return SUCCESS but empty content (Reproduce via: `https://raw.githubusercontent.com/lllyasviel/LayerDiffuse/main/README.md`).
    - **Safety Limits:** Implement `max-turns` (99) and `max-cost` ($5) limits in `config.yaml`, enforced strictly in `--yolo` (`-y`) mode.
    - **Context Robustness:** Recursive directory expansion for context paths; support remote URLs in `.context` files; strictly enforce deduplication.
    - **Pruning Threshold:** Refine `turn_context_threshold` logic to sum ONLY files from `turn.context` (scope: Turn). Exclude `session.context` and system prompts from the threshold calculation.
    - **Session Migration:** Cap turns at 99 (2-digit padding); at turn 100, automatically migrate to a new continuation session (e.g., `name-2`) by cloning `session.context` and the active prompt and transition the `turn.context` exactly as a normal turn transition would to preserve the working context.
    - **Action Side-effects:** `CREATE` and `EDIT` actions automatically add the target file path to the turn's context (provided the file exists).
    - **Architecture Polish:** Relocate agent prompts (e.g., `pathfinder.xml`) to session root; strictly deprecate turn-local prompts; implement session termination on empty message (no `report.md` created); prevent "Message Turns" from being pruned.
    - **Fail-Fast & Hardening:** Implement `EXECUTE` fail-fast on interactive prompts (UNIX: Signal-based; Windows: Exit-code based) with consistent "Interactive prompt detected" messaging; mid-execution consistency for `EDIT`.
    - **Relaxed Validation:** Allow `READ` of existing context and `EDIT` of non-context files; rely on matching logic for enforcement.
    - **Parser Resilience:** For all actions, ignore and clean up unforeseen codeblocks, thematic breaks (`---`), trailing text within both `~~~~~~` and ` `````` ` delimiters, and ALL unexpected codeblocks in the AST during parsing without triggering validation errors.
    - **Config Validation & Transient Retry:** Validate LLM configuration (API key, model) at startup, then retry on any error during LLM completion (default 3 attempts) or after configurable timeout without LLM response.
    - **Diagnostic Reporting:** Ensure `is_session` flag persists during validation failures to suppress redundant "Resource Contents" while preserving "Closest Match Diffs".
    - **Provider Routing & Display:** Remove `llm.provider` special-casing in `litellm_adapter`; extract actual provider from `_hidden_params["provider"]` after completion; persist provider in `meta.yaml`; display `model / provider` in TUI right panel metadata; document pass-through behavior of `llm` config section and `:nitro`/`:floor` shortcuts.
    - **Preserve User-Message Turns:** Protect action turns where the user provided an additional message during review from auto-pruning by checking report metadata.
    - **Web Content Caching (Session):** Cache web content from URLs in `session.context` and `turn.context` within a session to avoid redundant fetches; stored as a session-level cache file.
    - **Validation Failure Pruning Timing:** Modify Heuristic 4 in `session_pruning_service.py` to prune validation-failed turns ONLY when a subsequent report.md without "Validation Failed" status exists (a "non-VF report"). The guard checks for non-VF reports on disk (any turn with a report.md whose overall status is not "Validation Failed") and the current turn's status (`current_status` not containing "Validation Failed"). This is distinct from Heuristic 3's guard (green plan status) and ensures validation failure turns remain visible in context during chains of consecutive failures.
    - **Session Context Write-Time Dedup:** Add path deduplication in `SessionService._prepare_session_context()` before writing to `session.context`. Currently, `init.context` lines merged with `additional_context` can contain duplicates that are written to disk. Ensure the merged list is deduplicated so that `session.context` never contains duplicate paths at creation time. (Note: read-time dedup via `read_context_file` already handles the `session.context` → `resolve_context_paths` pipeline, but write-time dedup is a defensive best practice.)

### Milestone 3: TUI & UX Enhancements [PLANNED]
- **Core Goal:** Improve the interactive experience and provide better visibility into session state.
- **Specs:** [docs/project/specs/interactive-session-workflow.md](/docs/project/specs/interactive-session-workflow.md)
- **Requirements:**
    - **Navigation:** Alt+Up/Down for jumping between Context, Rationale, and Plan/Message sections.
    - **Context Interactions:** Pressing `e` on context nodes opens the corresponding file/context file in the external editor.
    - **Metadata Visibility:** Display model name and session cost (rounded to nearest cent) in the right panel when the Context Root is selected.
    - **Tier 2 Editing:** Automatically open external editor for parameters that are multiline or >100 characters.
    - **Editor & Diff Mapping:** Strictly respect `editor` config; implement a translation table for diff flags (e.g., `nvim` -> `-d`); remove all implicit VS Code fallbacks.
    - **Layout:** Ensure consistent padding for Rationale items and Message sections to match the right and left panels.
- **Proposed Vertical Slices:**
    - **`00-03-casefold-agent-name-comparison`:** Apply `.casefold()` to all remaining `stem ==` comparisons in `session_service.py` (lines 83, 522) and `session_repository.py` (line 139) for consistent case-insensitive agent name resolution. This fixes potential mismatches when session metadata or config files use capitalized names.
    - **`00-04-remove-bare-except-in-init-service`:** Fix the bare `except: pass` in `InitService._get_default_content()` (lines ~82-84) that catches `(yaml.YAMLError, OSError, ImportError, AttributeError)`. This silently swallows errors from `importlib.resources` API changes (Python 3.12+), returning `None` instead of template content. Action: replace with specific, logged error handling that re-raises unexpected errors, ensuring initialization failures are visible.

## Technical Debt


- Create a reusable pytest fixture (`ports_fixture`) in `tests/harness/setup/` that provides pre-configured port mocks with sensible defaults for `ISessionManager`, `IFileSystemManager`, etc. This reduces the risk of "mock poisoning" (bare MagicMock instances missing required `return_value` configurations) in test setup.
- `detect-secrets` falsely flags the API key placeholder (`api_key: ""`) in `README.md` as a "Secret Keyword". This is a pre-existing false positive in the documentation example config. To suppress it, the `.secrets.baseline` would need to be updated. For README-only changes, use `--no-verify` to bypass the false positive gate.
- **Silent error swallowing (Failure Transparency):** The Systemic Audit for Bug #07 revealed numerous `except` blocks across the codebase that silently catch `OSError`, `json.JSONDecodeError`, and other broad exception types without logging or re-raising. Affected files include: `cli_helpers.py`, `local_file_system_adapter.py`, `shell_adapter.py`, `web_scraper_adapter.py`, `yaml_config_adapter.py`, `action_executor.py`, `context_service.py`, `session_pruning_service.py`, `session_repository.py`, `update_checker.py`, `io.py`. While many of these are legitimate "safe to ignore" cases (cleaning up temp files, closing resources), several would benefit from debug-level logging before swallowing, consistent with the architectural standard of Failure Transparency.
- `perform_upgrade` and `should_update` in `update_checker.py` were removed as dead code (the update system is now notification-only). The legacy debt about `uv tool install` incompatibility is no longer relevant.
- The startup notification (`_display_update_notification`) was wired in both `handle_new_session` and `handle_resume_session` to display a non-blocking update notification after the background check thread starts.
- `auto_update` config key was removed from `config.yaml` as dead config (never read by production code).
- **Pre-existing Mypy errors in three files:**
  - `src/teddy_executor/core/services/action_executor.py:191` — Incompatible return value type (tuple[ActionLog, Any | str | None] vs tuple[ActionLog, str]).
  - `src/teddy_executor/core/services/session_orchestrator.py:251` — Item "DataclassInstance" has no attribute "agent_name" (union-attr).
  - `src/teddy_executor/adapters/outbound/openrouter_hydrator.py:17` — Untyped function body not checked (annotation-unchecked).
  These errors exist in the base code and are not introduced by any recent fix. They block pre-commit's Mypy hook, requiring `--no-verify` for commits. A dedicated fix slice should address these by adding proper type annotations and fixing return type mismatches.

- **pip-audit pre-commit hook:** The pip-audit hook in `.pre-commit-config.yaml` flags 15 known vulnerabilities across 4 transitive dependencies (aiohttp, litellm, msgpack, python-dotenv). All are assessed as **Low practical risk** for TeDDy:
  - **aiohttp (11 vulns):** Server-side issues (DoS, request smuggling) — TeDDy only uses aiohttp as an async HTTP client, not a server.
  - **litellm (2 vulns):** Proxy SQLi (High) and Auth Bypass via Host Header (Critical) — TeDDy uses the client SDK only, no proxy server.
  - **msgpack (1 vuln):** Potential DoS via crafted input — TeDDy serializes standard types with trusted data only.
  - **python-dotenv (1 vuln):** Path traversal in .env loading — TeDDy runs in controlled environments with a single config file.
  - **Blocker:** All four packages are transitively pinned by litellm 1.83.7. Upgrading any of them requires also upgrading litellm, but all litellm versions ≥1.83.8 dropped Python 3.14 support via `requires-python <3.14`. Our CI is now fully on Python 3.14, so we cannot upgrade without breaking installation. Fix blocked until upstream lifts the cap: [litellm#26343](https://github.com/BerriAI/litellm/issues/26343).
