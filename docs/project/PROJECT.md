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

### Milestone 3: Foundational Refactors [PLANNED]
- **Core Goal:** Eliminate redundant blueprint definitions across all 6 agent prompts by extracting shared content into `docs/templates/`, and reduce prompt maintenance burden by injecting MRP + common general rules from a central `MRP.xml` base prompt.
- **Specs:** TBD
- **Requirements:**
    - **Blueprint Extraction to docs/templates/:** Remove all `<blueprints>` sections from every agent XML prompt (pathfinder, architect, developer, debugger, assistant, prototyper). Replace them with a directive in each agent's workflow instructions to "use the corresponding template from `docs/templates/` when creating an artifact." Create `docs/templates/` populated with default Markdown template files for: Specification Document, Task Brief, Case File, Vertical Slice, Milestone, Component Design Document, ARCHITECTURE.md (Conventions section), PROJECT.md (Roadmap section). Add `teddy init templates` subcommand to regenerate `docs/templates/` from defaults. `teddy init` (without subcommand) also creates `docs/templates/` on first init.
    - **MRP.xml Base Prompt:** Extract the Markdown Response Protocol (MRP) from `<response_format>` and common `<general_rules>` (rules 1-9, plus Conflict Resolution and Programmatic Edits) from all 6 agent XMLs into a single `MRP.xml` file. This base prompt is appended after the agent-specific XML at system prompt assembly time and is NOT copied to `.teddy/prompts/` for user modification. Agent-specific rules (e.g., Debugger's Remote Probing Protocol, Developer's Contract Enforcement) remain in their respective XMLs.
    - **Makefile Template (docs/templates/makefile.md):** Create a Makefile template defining executable commands for the VCP commit workflow and the Debugger's Remote Probing Protocol. Defines `make commit 'message'` for the VCP workflow (stages, pre-commit runs, commits, and pushes) and `make probe 'reason'` for the Remote Probing Protocol (pushes probe, triggers CI workflow, retrieves logs). This template serves as the reference for Milestone 0 bootstrapping — teams implement their project-specific Makefile following this pattern. The PROJECT.md template links to this file.
- **Guidelines:**
    - Blueprint extraction is a content-only change to agent XMLs and a file generation change to InitService — zero architecture changes to PromptManager.
    - MRP.xml requires a PromptManager change to prepend/append the base prompt at resolution time.
    - The makefile template defines the command interface; TeDDy does NOT create the Makefile directly — teams implement it during Milestone 0.

### Milestone 4: TUI & UX Enhancements [PLANNED]
- **Core Goal:** Improve the interactive experience, provide better visibility into session state, and add foundational quality-of-life features.
- **Specs:** [docs/project/specs/interactive-session-workflow.md](/docs/project/specs/interactive-session-workflow.md)
- **Requirements:**
    - **Navigation:** Alt+Up/Down for jumping between Context, Rationale, and Plan/Message sections. If at the bottom, scroll page down instead of looping to top. Allow jumping between context sub-sections (system, session, turn).
    - **Context Interactions:** Pressing `e` on context nodes: if on session/turn root node, open corresponding `.context` file; if on a specific filepath, open the file; if on system node, show agent switch menu.
    - **Metadata Visibility:** Display model name and session cost (rounded to nearest cent) in the right panel when the Context Root is selected. Align rounding to cents (not fractions of cents).
    - **Tier 2 Editing:** Automatically open external editor for parameters that are multiline or >100 characters. Prevent multi-line break up for long text — if long text or multiline is detected, edit in editor instead of directly in TUI.
    - **Editor & Diff Mapping:** Strictly respect `editor` config; implement a translation table for diff flags (e.g., `nvim` -> `-d`); remove all implicit VS Code fallbacks.
    - **Layout:** Ensure consistent padding for Rationale items and Message sections to match the right and left panels. Apply same padding for both panels.
    - **MOVE & DELETE Actions:** Add `MOVE` and `DELETE` action types. Both should update context manifest files as well (renaming path/file name if moved, removing if deleted). `MOVE` can also be used for renaming. Both apply to files and folders.
    - **Configurable Limits:** Add `--max-turns` and `--max-cost` with sensible defaults (99 turns or $5 spent — set in config.yaml). These only apply in `-y` mode and are not cumulative (on `teddy resume`, start counting from 0).
    - **Configurable Tree Depth:** Add `max-project-tree-depth` config setting with omission indicators for truncated directories.
    - **Session Interrupt:** Add a way to interrupt a session (e.g., press `q`, then confirm with Enter).
    - **`--yolo` as Default:** Make `--yolo` mode a configurable default setting.
    - **Deprecate `--console`:** Mark `--console` mode as deprecated. Remove related dead code in a follow-up milestone.
- **Proposed Vertical Slices:**
    - **`00-03-cli-arg-normalization`:** Apply casefold to all remaining `stem ==` comparisons in `session_service.py` (lines 83, 522), `session_repository.py` (line 139), and make the prompt lookup in `prompts.py` case-insensitive. Additionally, normalize context paths from the `-c` flag by stripping leading slash, `./` prefix, and normalizing backslashes before seeding `session.context`. This fixes two bugs: case-sensitive agent name matching and verbatim path appending without normalization.
    - **`00-04-remove-bare-except-in-init-service`:** Fix the bare `except: pass` in `InitService._get_default_content()` (lines ~82-84) that catches `(yaml.YAMLError, OSError, ImportError, AttributeError)`. This silently swallows errors from `importlib.resources` API changes (Python 3.12+), returning `None` instead of template content. Action: replace with specific, logged error handling that re-raises unexpected errors, ensuring initialization failures are visible.

### Milestone 5: Quality Gate & Debt Reconciliation [PLANNED]
- **Core Goal:** Remove unnecessary inline quality bypasses, deprecate `--console` mode and related dead code, and eliminate redundant test coverage.
- **Specs:** TBD
- **Requirements:**
    - **Audit Inline Quality Bypasses:** Find and remove all unnecessary inline suppression comments (`# noqa`, `# pylint: disable`, `# type: ignore`) that mask real issues or are no longer needed. These bypasses allow code to bypass quality gates without justification.
    - **Deprecate `--console` Mode:** Remove the `--console` mode and all related dead code paths.
    - **Remove Redundant Tests:** Audit the test suite for acceptance tests that duplicate unit coverage, or tests that exist only to satisfy coverage targets without verifying real behavior. Remove redundant tests.
    - **Fix Pre-existing Mypy Errors:** Resolve the three known Mypy errors that block the pre-commit Mypy hook:
        - `action_executor.py:191` — Incompatible return value type.
        - `session_orchestrator.py:251` — Union-attr on DataclassInstance.
        - `openrouter_hydrator.py:17` — Untyped function body.
    - **Fix Pre-existing C901 Complexity:** Refactor the `parse` method in `markdown_plan_parser.py` (cyclomatic complexity 10, threshold 9) by extracting preamble stripping, normalization, and AST validation steps into smaller helper methods.
    - **Audit Quality Gate Bypasses in Git History:** Check for any `--no-verify` commits logged in Technical Debt and verify the bypasses are still justified or can be resolved.

## Technical Debt

- `preview_edit_diff_viewer()` in `textual_plan_reviewer_editor.py` uses a raw `subprocess.Popen` call with DEVNULL streams (line 157-163) instead of the centralized `ISystemEnvironment.run_command(background=True)` method. This duplicates the TTY detachment pattern and bypasses the `system_environment_adapter.py` abstraction. After the bug #23 fix, this location also needs updating to inherit std streams. Ideally, it should be refactored to use `run_command(background=True)` to ensure consistent behavior across all background subprocess launches.


- Create a reusable pytest fixture (`ports_fixture`) in `tests/harness/setup/` that provides pre-configured port mocks with sensible defaults for `ISessionManager`, `IFileSystemManager`, etc. This reduces the risk of "mock poisoning" (bare MagicMock instances missing required `return_value` configurations) in test setup.
- `detect-secrets` falsely flags the API key placeholder (`api_key: ""`) in `README.md` as a "Secret Keyword". This is a pre-existing false positive in the documentation example config. To suppress it, the `.secrets.baseline` would need to be updated. For README-only changes, use `--no-verify` to bypass the false positive gate.
- **Silent error swallowing (Failure Transparency):** The Systemic Audit for Bug #07 revealed numerous `except` blocks across the codebase that silently catch `OSError`, `json.JSONDecodeError`, and other broad exception types without logging or re-raising. Affected files include: `cli_helpers.py`, `local_file_system_adapter.py`, `shell_adapter.py`, `web_scraper_adapter.py`, `yaml_config_adapter.py`, `action_executor.py`, `context_service.py`, `session_pruning_service.py`, `session_repository.py`, `update_checker.py`, `io.py`. While many of these are legitimate "safe to ignore" cases (cleaning up temp files, closing resources), several would benefit from debug-level logging before swallowing, consistent with the architectural standard of Failure Transparency.
- `perform_upgrade` and `should_update` in `update_checker.py` were removed as dead code (the update system is now notification-only). Upgrade instructions now use `uv tool upgrade teddy-cli`.
- The startup notification (`_display_update_notification`) was wired in both `handle_new_session` and `handle_resume_session` to display a non-blocking update notification after the background check thread starts.
- `auto_update` config key was removed from `config.yaml` as dead config (never read by production code).
- **Pre-existing Mypy errors in three files (block pre-commit Mypy hook):**
  - `src/teddy_executor/core/services/action_executor.py:191` — Incompatible return value type (tuple[ActionLog, Any | str | None] vs tuple[ActionLog, str]).
  - `src/teddy_executor/core/services/session_orchestrator.py:251` — Item "DataclassInstance" has no attribute "agent_name" (union-attr).
  - `src/teddy_executor/adapters/outbound/openrouter_hydrator.py:17` — Untyped function body not checked (annotation-unchecked).
  These errors exist in the base code and are not introduced by any recent fix. They block pre-commit's Mypy hook, requiring `--no-verify` for commits. A dedicated fix slice should address these by adding proper type annotations and fixing return type mismatches.

- **Pre-existing C901 complexity in `markdown_plan_parser.py`:** The `parse` method has a cyclomatic complexity of 10 (threshold 9). This is a pre-existing issue encountered during Bug #14's commit. It blocks the Ruff linter pre-commit hook. A dedicated refactor slice should extract the preamble stripping, normalization, and AST validation steps into smaller helper methods.

- pip-audit pre-commit hook: The pip-audit hook in `.pre-commit-config.yaml` flags 15 known vulnerabilities across 4 transitive dependencies (aiohttp, litellm, msgpack, python-dotenv). All are assessed as **Low practical risk** for TeDDy:
  - **aiohttp (11 vulns):** Server-side issues (DoS, request smuggling) — TeDDy only uses aiohttp as an async HTTP client, not a server.
  - **litellm (2 vulns):** Proxy SQLi (High) and Auth Bypass via Host Header (Critical) — TeDDy uses the client SDK only, no proxy server.
  - **msgpack (1 vuln):** Potential DoS via crafted input — TeDDy serializes standard types with trusted data only.
  - **python-dotenv (1 vuln):** Path traversal in .env loading — TeDDy runs in controlled environments with a single config file.
  - **Blocker:** All four packages are transitively pinned by litellm 1.83.7. Upgrading any of them requires also upgrading litellm, but all litellm versions ≥1.83.8 dropped Python 3.14 support via `requires-python <3.14`. Our CI is now fully on Python 3.14, so we cannot upgrade without breaking installation. Fix blocked until upstream lifts the cap: [litellm#26343](https://github.com/BerriAI/litellm/issues/26343).

  - **2026-08-24:** `--no-verify` was used for the `v0.1.13` release commit (`8794fe6d`, `chore(release): bump version to 0.1.13 with hotfix release notes`) to bypass the pre-existing pip-audit block documented above. The staged changes were purely a version bump in `pyproject.toml` and the addition of release notes.

  - **2026-08-26:** `--no-verify` was used for the Bug #23 editor TTY fix commit to bypass pre-existing TID251 violations (`unittest.mock.patch` and `MagicMock` banned in test files) in `test_tui_view_plan_robustness.py` and `test_system_environment_adapter_kwargs.py`. These violations are pre-existing (both files used `patch`/`MagicMock` before this bug fix) and are scheduled for resolution in Milestone 5 (Quality Gate & Debt Reconciliation). The staged changes include the actual fix (3 lines in 2 production files), updated regression tests, and this case file.
