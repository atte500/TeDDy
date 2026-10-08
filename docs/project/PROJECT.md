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
- **Spec Organization:** Specification documents are split by lifecycle into two subfolders: `docs/project/specs/invariants/` (formats, contracts, and workflows of record — long-lived system invariants) and `docs/project/specs/features/` (to-be-implemented initiatives that feed the `Spec -> Milestone -> Slice` lifecycle — deleted per the Archiving Policy once implemented).
- **Release Process:** The release process follows these steps:
    1. **Triage:** Determine the scope (patch, minor, major) by reviewing `git log v<last_tag>..HEAD` for conventional commits.
    2. **Release Notes:** Create a new file at `docs/project/releases/v<new_version>.md` summarizing features and fixes from the commit log.
    3. **Version Bump:** Update the `version` field in `pyproject.toml`.
    4. **Approval Gate:** Present the proposed release notes and version bump to the user for review and approval.
    5. **Commit:** Stage changes (including `uv.lock` if it was modified by the version bump build) and commit with `chore(release): bump version to <new_version>`.
    6. **Tag:** Create a local tag with `git tag -a v<new_version> -m "v<new_version>"` and push it with `git push origin v<new_version>`.
    7. **Publish:** Create a GitHub Release using `gh release create v<new_version> --title "v<new_version>" --notes-file docs/project/releases/v<new_version>.md`.

## Roadmap

### Milestone 3: Foundational Refactors [PLANNED]
- **Core Goal:** Eliminate redundant blueprint definitions across all 6 agent prompts by extracting shared content into `docs/templates/`, and reduce prompt maintenance burden by injecting MRP + common general rules from a central `MRP.xml` base prompt. Enhance the editor configuration UX with early validation, discovery, and persistence.
- **Specs:** N/A (editor-validation spec retired — feature shipped as slice 03-01)
- **Requirements:**
    - **Editor Validation & Discovery (03-01):** Change default editor config to empty string. Add `discover_editors()` method to ConsoleToolingHelper for scanning PATH. Validate configured editor availability during preflight check. Prompt for interactive selection when no editor is configured or the configured one is missing. Persist selection to `.teddy/config.yaml`. Support "disabled" sentinel for graceful disablement. Fall back to file-opening (no diff flags) for unknown editors in diff viewer, with `diff_flags` config override. Add `set_setting()` method to `IConfigService`/`YamlConfigAdapter`.
    - **Blueprint Extraction to docs/templates/ (03-03):** Remove all `<blueprints>` sections from every agent XML prompt (pathfinder, architect, developer, debugger, assistant, prototyper). Replace them with a directive in each agent's workflow instructions to "use the corresponding template from `docs/templates/` when creating an artifact." Create `docs/templates/` populated with default Markdown template files for: Specification Document, Task Brief, Case File, Vertical Slice, Milestone, Component Design Document, ARCHITECTURE.md (Conventions section), PROJECT.md (Roadmap section). Add `teddy init templates` subcommand to regenerate `docs/templates/` from defaults. `teddy init` (without subcommand) also creates `docs/templates/` on first init.
    - **MRP.xml Base Prompt (03-02):** Extract the Markdown Response Protocol (MRP) from `<response_format>` and common `<general_rules>` from all 6 agent XMLs into a single `MRP.xml` file. `PromptManager.fetch_system_prompt()` injects an `Agent Name: {agent}` line before the agent-specific XML, then appends MRP.xml after the agent-specific content (both inside the `<system>` tag). A legacy compatibility check skips MRP injection when a resolved prompt already contains `<response_format>`. It is NOT copied to `.teddy/prompts/` for user modification. Agent-specific rules (e.g., Debugger's Remote Probing Protocol, Developer's Contract Enforcement) remain in their respective XMLs.
    - **Makefile Template (docs/templates/makefile.md):** Create a Makefile template defining executable commands for the VCP commit workflow and the Debugger's Remote Probing Protocol. Defines `make commit 'message'` for the VCP workflow (stages, pre-commit runs, commits, and pushes) and `make probe 'reason'` for the Remote Probing Protocol (pushes probe, triggers CI workflow, retrieves logs). This template serves as the reference for Milestone 0 bootstrapping — teams implement their project-specific Makefile following this pattern. The PROJECT.md template links to this file.
- **Guidelines:**
    - Blueprint extraction is a content-only change to agent XMLs and a file generation change to InitService — zero architecture changes to PromptManager.
    - MRP.xml requires a PromptManager change to prepend/append the base prompt at resolution time.
    - The makefile template defines the command interface; TeDDy does NOT create the Makefile directly — teams implement it during Milestone 0.
    - Editor validation (03-01) is self-contained in outbound adapters and CLI handlers. No core domain logic changes. The `IConfigService.set_setting()` method is an additive breaking change to the protocol.

### Milestone 4: TUI & UX Enhancements [PLANNED]
- **Core Goal:** Improve the interactive experience, provide better visibility into session state, and add foundational quality-of-life features.
- **Specs:** [docs/project/specs/invariants/interactive-session-workflow.md](/docs/project/specs/invariants/interactive-session-workflow.md)
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

Tracks known technical debt for future cleanup.

**Format:** `- [Description including context and location of the debt item.]`

**Logging Hygiene (MUST):**
- **Never re-log the same debt.** If a debt item recurs across commits, fold the new occurrence into the existing entry — do NOT append a new bullet. A repeat finding is signal that the debt is unresolved, not a new item.
- **Prefer fixing directly over logging.** Only log debt that genuinely cannot be resolved in the moment. Do not log-then-resolve a defect that could be fixed immediately.
- **Never log resolved items.** Do not add "informational" or "completed" entries. The moment a debt item is addressed, delete its entry.

**Deletion Policy:** When a technical debt item is addressed (the underlying issue is resolved in a completed milestone/slice), the entry MUST be deleted from this section. Do not mark it as "completed" or "resolved" — remove it entirely. Git history serves as the permanent record.

### Open Debt

- **Inbound-port contract tests split across two directories.** Most `core.ports.inbound` contract tests live in `tests/suites/unit/core/ports/inbound/`, but `test_run_plan_use_case_contract.py` lives in the parallel `tests/suites/unit/ports/inbound/`. Consolidate into one canonical location.
- **Inconsistent manifest constants in `InitService`.** `_TEMPLATE_FILES` is a module-level constant (single-sourced with its unit test), but the prompt and config file manifests remain inline string literals inside `_init_prompts` and `_init_config_dir`. Extract symmetric `_PROMPT_FILES` / `_CONFIG_FILES` module constants for consistency and test reuse.
- **Pre-existing quality-gate violations block the pre-commit stage (consolidated).** The staged-file-scoped pre-commit hooks (Ruff, Mypy, Bandit) surface pre-existing violations in files a change set does not touch, forcing `--no-verify` for the pre-commit stage only (the post-commit full-suite test gate is never bypassed). Distinct findings: Mypy — `action_executor.py`, `console_interactor_ask_loop.py` (msvcrt/termios `attr-defined`), `textual_plan_reviewer_editor.py` (msvcrt), `textual_plan_reviewer_app.py`, `session_lifecycle_manager.py:92`, `tests/harness/setup/test_environment.py:27`. Ruff `C901` — `markdown_plan_parser.py::parse`, `litellm_adapter.py::get_completion`, `textual_plan_reviewer_editor.py::{launch_editor, preview_edit_diff_viewer}`, `console_interactor_ask_loop.py::_launch_editor_background`, `session_cli_handlers.py::_orchestrate_session_loop`. Ruff `PLR0911` — `parser_infrastructure.py::coerce_param`. Ruff `PLR0913`/`PLR0915` — `session_cli_handlers.py::_orchestrate_session_loop`, `ShellAdapter.execute` (PLR0913), and the `--message/-m` resume-threading signatures (`SessionLifecycleManager.resume`, `_consume_awaiting_reply`, `_handle_planning_and_execution`). Ruff `TID251` mock-ban — `tests/suites/unit/core/services/test_session_lifecycle_manager.py` and `tests/suites/unit/core/services/test_bug_03_prompt_resolution.py` (the out-of-scope `TestLifecyclePrintsInitialRequest` class). Bandit `B110` (`try/except/pass`) — `update_checker.py` (the dev-version parse guard in `fetch_latest_version`). All scheduled for Milestone 5.
- **Silent error swallowing (Failure Transparency).** Many `except` blocks across `cli_helpers.py`, `local_file_system_adapter.py`, `shell_adapter.py`, `web_scraper_adapter.py`, `yaml_config_adapter.py`, `action_executor.py`, `context_service.py`, `session_pruning_service.py`, `session_repository.py`, `update_checker.py`, and `io.py` catch broad exception types without logging. Several are legitimate "safe to ignore" cases; the rest should add debug-level logging before swallowing.
- **pip-audit vulnerabilities (blocked upstream).** The staged-file pre-commit `pip-audit` hook reports known vulnerabilities across transitive deps (latest run: 38 advisories across 11 packages — aiohttp, litellm, urllib3, werkzeug, soupsieve, multidict, h2, click, python-dotenv, pip, virtualenv), all assessed Low practical risk (client-only usage). The hook also warns it audits a different virtualenv than the active checkout (`.../TeDDy/.venv` vs `.../TeDDy2/.venv`), so the reported counts may drift until `PIPAPI_PYTHON_LOCATION` pins the active interpreter. Blocker: the runtime deps are transitively pinned by litellm 1.83.7, and upgrading requires litellm >=1.83.8, which dropped Python 3.14 (our CI target). Fix blocked until upstream lifts the cap: [litellm#26343](https://github.com/BerriAI/litellm/issues/26343).
- **VCP POSIX-shell friction on Windows.** The Debugger's standard VCP codeblock uses POSIX-only shell constructs (comment lines, `|| [ -z "$(git remote)" ]`) that cmd.exe cannot parse. Workaround: split into shell-agnostic single-line git commands. Candidate for the VCP/Makefile workflow improvement in Milestone 5.
- **Duplicated literals/format strings (single-source candidates).** Several string literals are duplicated across production sites and must stay in lockstep: the `cl100k_base` encoding name (`litellm_adapter.py` + `cli_helpers.prewarm_imports`); the `TEDDY_LLM_API_KEY` env-var name (`session_cli_handlers.py` + bundled `config.yaml`); the `"disabled"` editor sentinel (`console_tooling.py` + `session_cli_handlers.py` + `test_environment.py`); the "Editor is disabled in config" message (`console_interactor_ask_loop.py` + `console_interactor.py`); the `## User Request` section format (`execution_report.md.j2` + `SessionLifecycleManager._append_user_request`); the `awaiting_reply` flag key (`session_orchestrator.py` + `session_lifecycle_manager.py`). Extract shared constants/helpers.
- **Duplicated logic/helpers (extraction candidates).** The "does this model require an API key?" check (delegating to `litellm.validate_environment`) is duplicated in `LiteLLMAdapter.validate_config` and `_llm_model_requires_api_key`; the MESSAGE-action detection iteration is duplicated in `session_orchestrator.py`; the preservation-arm decision is mirrored in `SessionService.transition_to_next_turn` and `preserve_turn_in_session_context`; two function-local imports from `session_orchestrator` exist in `session_lifecycle_manager.py`. Single-source each.
- **Shared test-fake extraction (rule of three met).** Multiple bespoke in-memory test doubles are duplicated across suites: three dict-backed `InMemoryFileSystem` fakes (`test_session_repository_meta_contract.py`, `test_session_service_turn_meta.py`, `test_session_lifecycle_resume_message_persistence.py`); four `termios` fakes (`test_tty_guards.py`, `test_terminal_cooked_mode_restore.py`, `test_restore_cooked_mode.py`, `test_terminal_quit_key_listener_reader.py`); ask-loop editor/tooling fakes across three suites. Also: extract a `ports_fixture` of pre-configured port mocks to reduce mock-poisoning risk. Consolidate into `tests/harness/setup/`.
- **Duplicated temp-root context-manager boilerplate (harness fakes).** `tests/harness/setup/model_registry_cache.py` and `hook_shims.py` each duplicate the `tempfile.mkdtemp()` + `rmtree` lifecycle. Extract a shared temp-root helper.
- **Dual `## Resource Contents` render sites in `execution_report.md.j2`.** `report.failed_resources` and the classified `resource_logs` collector currently cover disjoint paths (no live duplication), but a future bridge could re-introduce the Bug 53 divergent-duplicate-gating class. Consolidate into the single classification pass.
- **Bespoke surgical YAML line-editor in `YamlConfigAdapter.set_setting`.** Hand-rolled indentation-aware key scanner + value rewriter + degenerate-root stripper + key inserter, existing only to avoid a `ruamel.yaml` dependency. Re-evaluate consolidating onto `ruamel.yaml` if that dependency is accepted.
- **Dead code pending confirmation/removal.** `IUserInteractor.confirm_plan_review` (no production call site) and `InterruptGuard.enter_waiting()` (no production call site) — decide wire-or-remove.
- **Under-specified "interrupted-at-a-reply" session state.** Only the pipeline-stop path records the `awaiting_reply` flag; the interactive-interruption path does not, forcing the resume state machine to infer intent from a missing flag plus the pending plan's shape. Single-source the state on both stop paths.
- **Order-dependent full-suite flake in `test_file_system_adapter_recursion.py`.** One full-suite run failed `test_list_directory_recursive_respects_ignores` (CWD leakage under pytest-xdist); passes in isolation and on re-run. Candidate: a CWD-snapshot Poka-Yoke fixture.
- **Pre-existing `PytestUnhandledThreadExceptionWarning` in the update-checker background thread.** `update_checker.py::write_update_cache` raised `FileExistsError` on the `.teddy` mkdir (`exist_ok=True`) under parallel xdist; guard against `FileExistsError`/`NotADirectoryError`.
- **TUI diff-routing predicate vs `diff_flags` config override.** The routing predicate reads the static `_DIFF_FLAGS` table while `get_diff_viewer_command()` honours the `diff_flags` override, so a user-supplied `diff_flags` is silently ignored for unknown editors. Single-source the "is this a registered diff editor?" decision.
- **Coincidentally-passing sibling test double in `test_planning_service_logging.py`.** `test_generate_plan_handles_zero_usage_gracefully` passes only via retry exhaustion; rebuild its `get_completion` double to drive a clean single generation.
- **`EditSimulator._apply_single_edit` relies on the matcher invariant.** It evaluates ambiguity before the threshold guard; correct only because the matcher now gates `is_ambiguous` on the effective threshold. Add the symmetric `and score >= threshold` guard for defence-in-depth.
- **Additive Protocol members vs hand-written contract doubles.** The hand-doubled `ISessionManager` contract double required manual migration for the additive `preserve_turn_in_session_context`. Document the convention or replace with autospec-based contract checks.
- **MRP test resource-root setup duplicated across two suites.** The real-`tmp_path` `MRP.xml` resource-root construction in `tests/suites/unit/core/services/test_prompt_manager.py` is duplicated in `test_bug_03_prompt_resolution.py`. Extract a shared harness helper once a third consumer appears (rule of three not yet met).
