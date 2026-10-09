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
- **Spec Organization:** Specification documents live in a single flat directory `docs/project/specs/` and are reserved strictly for **permanent system invariants** — formats, contracts, protocols (e.g. the MRP), core data models, and non-negotiable architectural rules. Feature goals, requirements, and acceptance criteria belong in Milestone documents (`docs/project/milestones/`), not in specs. There is no ephemeral `specs/features/` lifecycle.
- **Release Process:** The release process follows these steps:
    1. **Triage:** Determine the scope (patch, minor, major) by reviewing `git log v<last_tag>..HEAD` for conventional commits.
    2. **Release Notes:** Create a new file at `docs/project/releases/v<new_version>.md` summarizing features and fixes from the commit log.
    3. **Version Bump:** Update the `version` field in `pyproject.toml`.
    4. **Approval Gate:** Present the proposed release notes and version bump to the user for review and approval.
    5. **Commit:** Stage changes (including `uv.lock` if it was modified by the version bump build) and commit with `chore(release): bump version to <new_version>`.
    6. **Tag:** Create a local tag with `git tag -a v<new_version> -m "v<new_version>"` and push it with `git push origin v<new_version>`.
    7. **Publish:** Create a GitHub Release using `gh release create v<new_version> --title "v<new_version>" --notes-file docs/project/releases/v<new_version>.md`.

## Roadmap

### Milestone 3: Foundational Refactors [COMPLETED]
- **Core Goal:** Eliminate redundant blueprint definitions across all 6 agent prompts by extracting shared content into `docs/templates/`, and reduce prompt maintenance burden by injecting MRP + common general rules from a central `MRP.xml` base prompt. Enhance the editor configuration UX with early validation, discovery, and persistence.
- **Specs:** N/A (editor-validation spec retired — feature shipped as slice 03-01)
- **Requirements:**
    - **Editor Validation & Discovery (03-01):** Change default editor config to empty string. Add `discover_editors()` method to ConsoleToolingHelper for scanning PATH. Validate configured editor availability during preflight check. Prompt for interactive selection when no editor is configured or the configured one is missing. Persist selection to `.teddy/config.yaml`. Support "disabled" sentinel for graceful disablement. Fall back to file-opening (no diff flags) for unknown editors in diff viewer, with `diff_flags` config override. Add `set_setting()` method to `IConfigService`/`YamlConfigAdapter`.
    - **Blueprint Extraction to docs/templates/ (03-03):** Remove all `<blueprints>` sections from every agent XML prompt (pathfinder, architect, developer, debugger, assistant, prototyper). Replace them with a directive in each agent's workflow instructions to "use the corresponding template from `docs/templates/` when creating an artifact." Create `docs/templates/` populated with default Markdown template files for: Specification Document, Task Brief, Case File, Vertical Slice, Milestone, Component Design Document, ARCHITECTURE.md (Conventions section), PROJECT.md (Roadmap section). Add `teddy init templates` subcommand to regenerate `docs/templates/` from defaults. `teddy init` (without subcommand) no longer creates `docs/templates/` on first init.
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
    - **Audit Quality Gate Bypasses in Git History:** Check Git history for any `--no-verify` commits and verify the bypasses are still justified or can be resolved.
    - **Re-homed Debt Reconciliation:** The quality-gate, reliability, and specific-defect items formerly parked in the retired `## Technical Debt` section are now scheduled as Vertical Slices in the milestone document (`docs/project/milestones/05-quality-gate-debt-reconciliation.md`). Cross-cutting duplication/consolidation items are scheduled in Milestone 6.

### Milestone 6: Cross-Cutting Consolidation [PLANNED]
- **Core Goal:** Eliminate duplicated literals, helpers, and test doubles that must be kept in manual lockstep; consolidate split test organization; and perform a bounded Failure-Transparency sweep. Every item was formerly parked in the retired `## Technical Debt` section and is now scheduled as an explicit requirement in `docs/project/milestones/06-cross-cutting-consolidation.md`.
- **Specs:** TBD
- **Requirements:**
    - **Single-source production literals & helpers:** Extract duplicated constants (the `cl100k_base` encoding name, the `TEDDY_LLM_API_KEY` env-var name, the `"disabled"` editor sentinel, the "Editor is disabled in config" message, the `## User Request` section format, the `awaiting_reply` flag key) and duplicated helpers (the API-key check, the MESSAGE-action detection iteration, the preservation-arm decision, the function-local `session_orchestrator` imports) into their canonical modules.
    - **Shared test-fake extraction:** Consolidate bespoke in-memory filesystem, `termios`, and ask-loop fakes into `tests/harness/setup/`, plus a shared `ports_fixture` of pre-configured port mocks and a shared temp-root helper.
    - **Directory consolidation:** Merge the split inbound-port contract-test directory (`tests/suites/unit/ports/inbound/`) into the canonical `tests/suites/unit/core/ports/inbound/`.
    - **InitService manifest symmetry:** Extract a `_CONFIG_FILES` module constant to match `_TEMPLATE_FILES`/`_PROMPT_FILES`.
    - **TUI diff-routing predicate:** Single-source the "is this a registered diff editor?" decision so the `diff_flags` override is honoured for unknown editors.
    - **Failure-Transparency sweep:** Narrow or add debug-level logging to broad `except` blocks across `cli_helpers.py`, `local_file_system_adapter.py`, `shell_adapter.py`, `web_scraper_adapter.py`, `yaml_config_adapter.py`, `action_executor.py`, `context_service.py`, `session_pruning_service.py`, `session_repository.py`, `update_checker.py`, and `io.py`.

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
