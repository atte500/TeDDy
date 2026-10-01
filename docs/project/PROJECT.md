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
- **Release Process:** The release process follows these steps:
    1. **Triage:** Determine the scope (patch, minor, major) by reviewing `git log v<last_tag>..HEAD` for conventional commits.
    2. **Release Notes:** Create a new file at `docs/project/releases/v<new_version>.md` summarizing features and fixes from the commit log.
    3. **Version Bump:** Update the `version` field in `pyproject.toml`.
    4. **Approval Gate:** Present the proposed release notes and version bump to the user for review and approval.
    5. **Commit:** Stage changes (including `uv.lock` if it was modified by the version bump build) and commit with `chore(release): bump version to <new_version>`.
    6. **Tag:** Create a local tag with `git tag -a v<new_version> -m "v<new_version>"` and push it with `git push origin v<new_version>`.
    7. **Publish:** Create a GitHub Release using `gh release create v<new_version> --title "v<new_version>" --notes-file docs/project/releases/v<new_version>.md`.

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
- **Core Goal:** Eliminate redundant blueprint definitions across all 6 agent prompts by extracting shared content into `docs/templates/`, and reduce prompt maintenance burden by injecting MRP + common general rules from a central `MRP.xml` base prompt. Enhance the editor configuration UX with early validation, discovery, and persistence.
- **Specs:** [docs/project/specs/editor-validation-and-discovery.md](/docs/project/specs/editor-validation-and-discovery.md)
- **Requirements:**
    - **Editor Validation & Discovery (03-01):** Change default editor config to empty string. Add `discover_editors()` method to ConsoleToolingHelper for scanning PATH. Validate configured editor availability during preflight check. Prompt for interactive selection when no editor is configured or the configured one is missing. Persist selection to `.teddy/config.yaml`. Support "disabled" sentinel for graceful disablement. Fall back to file-opening (no diff flags) for unknown editors in diff viewer, with `diff_flags` config override. Add `set_setting()` method to `IConfigService`/`YamlConfigAdapter`.
    - **Blueprint Extraction to docs/templates/ (03-02):** Remove all `<blueprints>` sections from every agent XML prompt (pathfinder, architect, developer, debugger, assistant, prototyper). Replace them with a directive in each agent's workflow instructions to "use the corresponding template from `docs/templates/` when creating an artifact." Create `docs/templates/` populated with default Markdown template files for: Specification Document, Task Brief, Case File, Vertical Slice, Milestone, Component Design Document, ARCHITECTURE.md (Conventions section), PROJECT.md (Roadmap section). Add `teddy init templates` subcommand to regenerate `docs/templates/` from defaults. `teddy init` (without subcommand) also creates `docs/templates/` on first init.
    - **MRP.xml Base Prompt (03-03):** Extract the Markdown Response Protocol (MRP) from `<response_format>` and common `<general_rules>` (rules 1-9, plus Conflict Resolution and Programmatic Edits) from all 6 agent XMLs into a single `MRP.xml` file. This base prompt is appended after the agent-specific XML at system prompt assembly time and is NOT copied to `.teddy/prompts/` for user modification. Agent-specific rules (e.g., Debugger's Remote Probing Protocol, Developer's Contract Enforcement) remain in their respective XMLs.
    - **Makefile Template (docs/templates/makefile.md):** Create a Makefile template defining executable commands for the VCP commit workflow and the Debugger's Remote Probing Protocol. Defines `make commit 'message'` for the VCP workflow (stages, pre-commit runs, commits, and pushes) and `make probe 'reason'` for the Remote Probing Protocol (pushes probe, triggers CI workflow, retrieves logs). This template serves as the reference for Milestone 0 bootstrapping — teams implement their project-specific Makefile following this pattern. The PROJECT.md template links to this file.
- **Guidelines:**
    - Blueprint extraction is a content-only change to agent XMLs and a file generation change to InitService — zero architecture changes to PromptManager.
    - MRP.xml requires a PromptManager change to prepend/append the base prompt at resolution time.
    - The makefile template defines the command interface; TeDDy does NOT create the Makefile directly — teams implement it during Milestone 0.
    - Editor validation (03-01) is self-contained in outbound adapters and CLI handlers. No core domain logic changes. The `IConfigService.set_setting()` method is an additive breaking change to the protocol.

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
    - **Session Interrupt:** Add a way to interrupt a session (e.g., press `q`, then confirm with Enter). Partially delivered ad-hoc via [00-21-session-interrupt-resume-message.md](/docs/project/tasks/00-21-session-interrupt-resume-message.md) (Ctrl+C two-phase interrupt, pipeline MESSAGE suppression, `resume -m`); TUI `q`-during-execution remains here.
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

## Failed Release Recovery

If a release needs to be redone (e.g., CI failures, missing assets):
1. **Delete** the GitHub release: `gh release delete v<version> --yes`
2. **Delete** the local and remote tags:
   ```shell
   git tag -d v<version>
   git push --delete origin v<version>
   ```
3. **Fix** the underlying issues (CI config, test failures, missing files).
4. **Ensure** `uv.lock` is staged alongside other changes to avoid a separate cleanup commit.
5. **Re-tag and release** following the standard Release Process from step 5 onward (commit, tag, push, publish).

## Technical Debt

- Create a reusable pytest fixture (`ports_fixture`) in `tests/harness/setup/` that provides pre-configured port mocks with sensible defaults for `ISessionManager`, `IFileSystemManager`, etc. This reduces the risk of "mock poisoning" (bare MagicMock instances missing required `return_value` configurations) in test setup.
- `detect-secrets` falsely flags the API key placeholder (`api_key: ""`) in `README.md` as a "Secret Keyword". This is a pre-existing false positive in the documentation example config. To suppress it, the `.secrets.baseline` would need to be updated. For README-only changes, use `--no-verify` to bypass the false positive gate.
- **Silent error swallowing (Failure Transparency):** The Systemic Audit for Bug #07 revealed numerous `except` blocks across the codebase that silently catch `OSError`, `json.JSONDecodeError`, and other broad exception types without logging or re-raising. Affected files include: `cli_helpers.py`, `local_file_system_adapter.py`, `shell_adapter.py`, `web_scraper_adapter.py`, `yaml_config_adapter.py`, `action_executor.py`, `context_service.py`, `session_pruning_service.py`, `session_repository.py`, `update_checker.py`, `io.py`. While many of these are legitimate "safe to ignore" cases (cleaning up temp files, closing resources), several would benefit from debug-level logging before swallowing, consistent with the architectural standard of Failure Transparency.
- **Completed cleanups (informational):** `perform_upgrade`/`should_update` were removed as dead code (the update system is notification-only; upgrade via `uv tool upgrade teddy-cli`); the startup notification (`_display_update_notification`) is wired in `handle_new_session` and `handle_resume_session` after the background check thread starts; the dead `auto_update` config key was removed from `config.yaml`.
- **Pre-existing Mypy errors in five files (block pre-commit Mypy hook; full set as of the windows-startup-latency contract commit, 2026-10-01):**
  - `src/teddy_executor/core/services/action_executor.py:208` — Incompatible return value type (tuple[ActionLog, Any | str | None] vs tuple[ActionLog, str]).
  - `src/teddy_executor/core/services/session_orchestrator.py:275` — Item "DataclassInstance"/"ABCMeta" of "DataclassInstance | type[DataclassInstance]" has no attribute "agent_name" (union-attr, x2).
  - `src/teddy_executor/adapters/outbound/console_interactor_ask_loop.py:101-102` — Module has no attribute "kbhit"/"getwch" (attr-defined; Windows-only `msvcrt` unresolvable on POSIX-host Mypy).
  - `src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py:184-185` — Module has no attribute "kbhit"/"getwch" (attr-defined; same msvcrt class).
  - `src/teddy_executor/adapters/inbound/textual_plan_reviewer_app.py:384` — Incompatible types in assignment (None vs str).
  - `tests/harness/setup/test_environment.py:27` — Incompatible types in assignment (harness setup file; surfaced by the staged-file-scoped Mypy hook's import graph during the windows-startup-latency Wiring commit, 2026-10-01 — the file itself was not modified by the triggering commits).
  - RESOLVED (windows-startup-latency Seam deliverable, 2026-10-01): `src/teddy_executor/adapters/outbound/openrouter_hydrator.py:17` — the untyped-body note was eliminated by typing the hydrator `__init__` (Constructor Injection seam); the note no longer appears in Mypy runs (confirmed absent from the Seam commit's pre-commit output).
  These errors exist in the base code and are not introduced by any recent fix (none of the affected files were modified by the triggering commits). They block pre-commit's Mypy hook, requiring `--no-verify` for commits (post-commit test gate is never bypassed). A dedicated fix slice should address these by adding proper type annotations, fixing return type mismatches, and isolating platform-specific imports (`msvcrt`/`termios`) behind typed accessors.

- **Pre-existing C901 complexity in `markdown_plan_parser.py`:** The `parse` method has a cyclomatic complexity of 10 (threshold 9). This is a pre-existing issue encountered during Bug #14's commit. It blocks the Ruff linter pre-commit hook. A dedicated refactor slice should extract the preamble stripping, normalization, and AST validation steps into smaller helper methods.

- pip-audit pre-commit hook: The pip-audit hook in `.pre-commit-config.yaml` flags 36 known vulnerabilities across 4 transitive dependencies (aiohttp, litellm, msgpack, python-dotenv; count grown from 15 as of the 2026-10-01 CI Quality Checks logs). All are assessed as **Low practical risk** for TeDDy:
  - **aiohttp (11 vulns):** Server-side issues (DoS, request smuggling) — TeDDy only uses aiohttp as an async HTTP client, not a server.
  - **litellm (2 vulns):** Proxy SQLi (High) and Auth Bypass via Host Header (Critical) — TeDDy uses the client SDK only, no proxy server.
  - **msgpack (1 vuln):** Potential DoS via crafted input — TeDDy serializes standard types with trusted data only.
  - **python-dotenv (1 vuln):** Path traversal in .env loading — TeDDy runs in controlled environments with a single config file.
  - **Blocker:** All four packages are transitively pinned by litellm 1.83.7. Upgrading any of them requires also upgrading litellm, but all litellm versions ≥1.83.8 dropped Python 3.14 support via `requires-python <3.14`. Our CI is now fully on Python 3.14, so we cannot upgrade without breaking installation. Fix blocked until upstream lifts the cap: [litellm#26343](https://github.com/BerriAI/litellm/issues/26343).

  - **Pre-existing PLR0911 in `coerce_param`:** The `coerce_param` function in `parser_infrastructure.py` has 9 return statements, exceeding Ruff's PLR0911 threshold of 6. This blocks the pre-commit Ruff linter hook for all commits that touch this file (or trigger a full lint scan on staged files with the same project-level lint). This is a pre-existing issue, not introduced by any recent change. Scheduled for resolution in Milestone 5 (Quality Gate & Debt Reconciliation).
- **VCP POSIX-shell friction:** the Debugger's standardized VCP execution codeblock uses POSIX-only shell constructs (`#` comment lines, `|| [ -z "$(git remote)" ]`) that cmd.exe cannot parse on Windows hosts (`: was unexpected at this time.`). Workaround: split the VCP into individual, shell-agnostic single-line `git` commands with `Allow Failure` replacing `|| true`. Candidate for the VCP/Makefile workflow improvement in Milestone 5.
- **PLR0913 on `ShellAdapter.execute`** (`shell_adapter.py:333`, 6 > 5 arguments — pre-existing signature, unchanged by recent fixes) and **Mypy `attr-defined` on `termios.tcflush`/`termios.TCIFLUSH`** in `console_interactor_ask_loop.py:92` (Windows-host Mypy cannot resolve the POSIX-only `termios` module). Both surfaced by the console-detachment fix commit's pre-commit run; scheduled for resolution in Milestone 5 (Quality Gate & Debt Reconciliation).
- Historical `--no-verify` bypasses (2026-08-24 through 2026-10-01) were all caused by pre-existing quality-gate violations (TID251 mock ban, pre-existing Mypy errors, bandit B404/B603/B605/B607/B110, pip-audit false positives) unrelated to the committed changes. Notable case (windows-startup-latency Seam commit, 2026-10-01): staging `registries/infrastructure.py` made the staged-file-scoped Mypy hook's import graph reach `console_interactor_ask_loop.py`, surfacing the pre-existing `msvcrt` attr-defined errors (lines 101-102; Windows-only module unresolvable on POSIX-host Mypy) — a documented Milestone 5 item, not a defect of the Seam changes (whose staged files are Mypy-clean; typing the hydrator `__init__` also resolved the `openrouter_hydrator.py:17` note in-scope). Forward-looking: any future commit staging `registries/infrastructure.py` (or any file whose import graph reaches the `console_interactor*` chain) trips the same gate until the Milestone 5 `msvcrt` typed-accessor fix lands. Per-commit references remain in git history and are covered by Milestone 5's "Audit Quality Gate Bypasses in Git History" requirement.
- **Duplicated temp-root context-manager boilerplate in harness fakes (Slice 00-20):** `tests/harness/setup/model_registry_cache.py` and `tests/harness/setup/hook_shims.py` each duplicate the `tempfile.mkdtemp()` + context-manager `rmtree` lifecycle (construction, `__enter__`, `__exit__` with `ignore_errors=True`). Census confirmed no shared temp-root helper exists in `tests/harness/setup/` (the `mkdtemp` hits in `composition.py:211` and `test_environment.py:44` are one-off usages, not reusable helpers). Candidate: extract a small shared temp-root base class/helper in `tests/harness/setup/` when a third file-state fake is added (rule of three). Scheduled for Milestone 5 (Quality Gate & Debt Reconciliation).
- **[DEBT] Dual `## Resource Contents` render sites in `execution_report.md.j2` (Bug #53 Systemic Audit):** The template renders resource content in two separate sections — `report.failed_resources` (validation-failure reports, populated by `cli_helpers.py`) and the classified `resource_logs` collector (execution reports). The audit verified these currently cover disjoint execution paths (validation-failure reports carry no enriched action logs; execution reports do not populate `failed_resources`; session mode suppresses both), so no live duplication exists. However, a future change bridging the two paths could re-introduce the divergent-duplicate-gating bug class of Bug 53. Candidate for consolidation into the single classification pass in Milestone 5 (Quality Gate & Debt Reconciliation).
- **[DEBT] Pre-existing lint/type/security debt surfaced by staging during the newline-determinism sweep commit (2026-10-01):** The staged-file-scoped local hooks exposed pre-existing violations in files touched only by formatting/one-line I/O edits: Ruff TID251 mock-ban (`MagicMock`/`patch`) ×8, PLR0915 ×2, F841 ×2 across the 3 TUI editor test files; Mypy errors in `test_tui_editor_suspend_resume.py` (`subprocess.CREATE_NO_WINDOW` attr-defined ×2, `index`); bandit B110 try/except-pass in `update_checker.py:115` (covered by the "Silent error swallowing" entry above); C901 in `markdown_plan_parser.py` (documented above). All pre-date the sweep — no semantic changes were made to these files. The sweep commit required `--no-verify` for the pre-commit stage only (the post-commit test gate remains enforced and passed). Milestone 5 (Quality Gate & Debt Reconciliation) scope.
