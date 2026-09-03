# Milestone 3: Foundational Refactors

- **Status:** In Progress
- **Specs:** [docs/project/specs/editor-validation-and-discovery.md](/docs/project/specs/editor-validation-and-discovery.md)

## Goal (The "Why")
Eliminate redundant blueprint definitions across all 6 agent prompts by extracting shared content into `docs/templates/`, and reduce prompt maintenance burden by injecting the Markdown Response Protocol (MRP) and common general rules from a central `MRP.xml` base prompt. This decouples shared template definitions from agent-specific instructions, making maintenance simpler and changes single-point updates.

## Proposed Solution (The "What")
Two workstreams will be executed as independent slices:

### Slice 03-01: Templates & Init
Bundled Markdown template files are stored in `src/teddy_executor/resources/templates/`. The `teddy init templates` subcommand copies them to `docs/templates/` in the user's project. The `teddy init` (bare) command also creates `docs/templates/` on first init. Agent XMLs have their `<blueprints>` sections replaced with directives referencing the templates. The PROJECT.md template (`project.md`) references `docs/templates/makefile.md` as part of Milestone 0 foundational tasks. Includes the Makefile template (`makefile.md`) as one of the 9 template files.

- **Auto-init on startup:** `teddy start` and `teddy resume` automatically create `docs/templates/` if the directory is missing (non-destructive — never overwrites existing files). Only `teddy init templates` forces overwrite.

### Slice 03-02: MRP Base Prompt
Extract the shared Markdown Response Protocol (response format + common general rules 1-9, plus Conflict Resolution and Programmatic Edits) that are duplicated identically across all 6 agents into `src/teddy_executor/resources/config/prompts/MRP.xml` (alongside the agent XMLs). PromptManager loads MRP.xml via `importlib.resources` and appends it at `fetch_system_prompt()` time. MRP.xml is NOT copied to `.teddy/prompts/` for user modification — it is protocol infrastructure.

## Guidelines (The "How")
- **Test Harness Strategy:**
    - **Blueprint Extraction:** Verify via `mock_fs` that `ensure_templates_initialized()` writes files to `docs/templates/`. Verify agent XMLs no longer contain `<blueprints>` sections via string search.
    - **MRP.xml Injection:** Verify via unit test that `fetch_system_prompt()` assembled content contains MRP protocol rules after agent-specific content. Verify `MRP.xml` is NOT written to `.teddy/prompts/` by `ensure_initialized()`.
    - **init templates Subcommand:** Verify via CLI adapter test that `teddy init templates` exists and produces expected output. Verify the `init` callback calls `ensure_templates_initialized()`.
- **Fail-Fast:** `fetch_system_prompt()` MUST raise `FileNotFoundError` if MRP.xml is missing from resources.
- **Shared Seam Strategy:** `fetch_system_prompt()` has 2 consumers — but the change is additive (non-breaking, signature unchanged). No migration needed.

## Technical Specifications
- **Prompt Resolution:** `PromptManager.fetch_system_prompt()` currently reads agent XML files from session root → `.teddy/prompts/`. For MRP.xml injection, the method loads MRP.xml from `src/teddy_executor/resources/config/prompts/MRP.xml` via `importlib.resources.files()` and appends its content after the resolved agent XML content.
- **Bundled Template Location:** `src/teddy_executor/resources/templates/` — alongside the existing `config/` resource package. Each template is a plain Markdown file.
- **Project Template Location:** `docs/templates/` — created by `teddy init` or `teddy init templates` in the user's project root.
- **File Locations (Source → Target):**
    - `src/teddy_executor/resources/templates/specification-document.md` → `docs/templates/specification-document.md`
    - `src/teddy_executor/resources/templates/task-brief.md` → `docs/templates/task-brief.md`
    - `src/teddy_executor/resources/templates/case-file.md` → `docs/templates/case-file.md`
    - `src/teddy_executor/resources/templates/vertical-slice.md` → `docs/templates/vertical-slice.md`
    - `src/teddy_executor/resources/templates/milestone.md` → `docs/templates/milestone.md`
    - `src/teddy_executor/resources/templates/component-design.md` → `docs/templates/component-design.md`
    - `src/teddy_executor/resources/templates/architecture.md` → `docs/templates/architecture.md`
    - `src/teddy_executor/resources/templates/project.md` → `docs/templates/project.md`
    - `src/teddy_executor/resources/templates/makefile.md` → `docs/templates/makefile.md`
    - `src/teddy_executor/resources/config/prompts/MRP.xml` — NOT copied (bundled only)
- **CLI Changes:**
    - Add `init_app.command()` named `templates` to `__main__.py` following the existing `prompts` and `config` pattern.
    - Modify `init_callback` to also call `ensure_templates_initialized()` when no subcommand is invoked.
- **IInitUseCase Changes:**
    - Add abstract method `ensure_templates_initialized(overwrite: bool = False) -> str`.
    - This is a BREAKING change to the ABC, but only one implementing class exists (`InitService`), making it a safe atomic change.
- **Agent XML Changes:**
    - Remove `<blueprints>` section entirely from all 6 agent XMLs.
    - Remove the duplicated `<general_rules>` (rules 1-9, 10, 11) and `<response_format>` blocks from all agent XMLs. These are now in MRP.xml.
    - Keep agent-specific rules (e.g., Debugger's Remote Probing Protocol rule 11, Developer's Contract Enforcement rule 10, Architect's programmatic edits rule 11).
    - Replace blueprint removal with a brief inline directive: e.g., `"Use the [Component Design template](/docs/templates/component-design.md) when creating blueprint artifacts."`

## Vertical Slices
- [ ] **03-01-Editor-Validation-and-Discovery** — Editor discovery, early PATH validation, interactive selection prompt, persistence to config, "disabled" sentinel handling, and diff flags fallback for unknown editors. See the [specification](/docs/project/specs/editor-validation-and-discovery.md) for full details.
- [ ] **03-02-Templates-and-Init** — Template files, `teddy init templates` subcommand, InitService changes, and blueprint removal from agent XMLs. See the [slice definition](/docs/project/slices/03-01-templates-and-init.md) for deliverables and scenarios.
- [ ] **03-03-MRP-Base-Prompt** — MRP.xml creation, PromptManager injection logic, and removal of shared general_rules/response_format from agent XMLs. See the [slice definition](/docs/project/slices/03-02-mrp-base-prompt.md) for deliverables and scenarios.
