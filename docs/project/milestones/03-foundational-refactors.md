# Milestone 3: Foundational Refactors

- **Status:** In Progress
- **Specs:** N/A (editor-validation spec retired — feature shipped as slice 03-01)

## Goal (The "Why")
Eliminate redundant common rules and response format definitions across all 6 agent prompts by extracting shared content into a central `MRP.xml` file. Reduce prompt maintenance burden and ensure protocol consistency by injecting agent name, agent-specific XML, and MRP.xml as a unified system prompt. The MRP is protocol infrastructure — NOT copied to `.teddy/prompts/` for user modification.

## Proposed Solution (The "What")
Two workstreams will be executed as independent slices:

### Slice 03-02: MRP Base Prompt & Agent Name Injection
Extract the shared Markdown Response Protocol (response format + common general rules) from all 6 agents into a single `src/teddy_executor/resources/config/prompts/MRP.xml` file. Modify `PromptManager.fetch_system_prompt()` to:
1. Inject an agent name line (`Agent Name: {agent}`) before the agent-specific XML at the start of the system prompt, so the agent can populate the `- **Agent:**` metadata in its plan.
2. Load MRP.xml via `importlib.resources.files()` and inject it after the agent-specific XML content (both inside the `<system>` tag).
3. Perform a legacy compatibility check: if the resolved agent prompt (from `.teddy/prompts/` override) already contains `<response_format>`, do NOT inject MRP.xml (preserve backward compatibility for customized prompts).
4. Raise `FileNotFoundError` if MRP.xml is missing from resources (fail-fast).

Agent XMLs have their duplicate common `<general_rules>` and `<response_format>` blocks removed, keeping only agent-specific rules. The MRP.xml state dashboard format instruction is a single shared directive rather than repeated per agent.

### Slice 03-03: Templates & Init
Bundled Markdown template files are stored in `src/teddy_executor/resources/templates/`. The `teddy init templates` subcommand copies them to `docs/templates/` in the user's project. The `teddy init` (bare) command also creates `docs/templates/` on first init. Agent XMLs have their `<blueprints>` sections replaced with directives referencing the templates. The PROJECT.md template (`project.md`) references `docs/templates/makefile.md` as part of Milestone 0 foundational tasks. Includes the Makefile template (`makefile.md`) as one of the 9 template files.

- **Auto-init on startup:** `teddy start` and `teddy resume` automatically create `docs/templates/` if the directory is missing (non-destructive — never overwrites existing files). Only `teddy init templates` forces overwrite.

## Guidelines (The "How")
- **Test Harness Strategy:**
    - **Blueprint Extraction:** Verify via `mock_fs` that `ensure_templates_initialized()` writes files to `docs/templates/`. Verify agent XMLs no longer contain `<blueprints>` sections via string search.
    - **MRP.xml Injection:** Verify via unit test that `fetch_system_prompt()` assembled content contains agent name line, agent-specific content, and MRP protocol rules. Verify MRP.xml is NOT written to `.teddy/prompts/` by `ensure_initialized()`.
    - **Legacy Check:** Verify that when `.teddy/prompts/{agent}.xml` contains `<response_format>`, the prompt does NOT include MRP.xml content.
    - **init templates Subcommand:** Verify via CLI adapter test that `teddy init templates` exists and produces expected output. Verify the `init` callback calls `ensure_templates_initialized()`.
- **Fail-Fast:** `fetch_system_prompt()` MUST raise `FileNotFoundError` if MRP.xml is missing from resources.
- **Shared Seam Strategy:** `fetch_system_prompt()` has 2 consumers — but the change is additive (signature unchanged). No migration needed.

## Technical Specifications
- **Prompt Resolution:** `PromptManager.fetch_system_prompt()` currently reads agent XML files from session root → `.teddy/prompts/`. For MRP.xml injection, the method:
    1. Resolves agent-specific XML content (existing logic).
    2. Injects `Agent Name: {agent}` as the first line of the assembled prompt.
    3. Appends MRP.xml content after agent-specific XML if the resolved prompt does NOT contain `<response_format>`.
- **Agent Name Injection:** The agent name is derived from the `agent_name` parameter passed to `fetch_system_prompt()`. Injected as `Agent Name: {agent}\n` before the agent XML opening tag.
- **Legacy Detection:** After resolving the prompt content (which may come from `.teddy/prompts/` user override), scan for `<response_format>` in the resolved string. If found, skip MRP injection entirely. This ensures users with custom prompts retaining their own response format are not forced to adopt MRP.
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
    - Remove the duplicated `<general_rules>` (common rules) and `<response_format>` blocks from all agent XMLs. These are now in MRP.xml.
    - Keep **only agent-specific rules** (e.g., Debugger's Remote Probing Protocol, Developer's Contract Enforcement rule 10 and Test Layer Isolation rule 11, Architect's programmatic edits rule 11 and Template-First Documentation rule 12, Prototyper's rule 10/12, Assistant's rule 12).
    - Replace blueprint removal with a brief inline directive: e.g., `"Use the [Component Design template](/docs/templates/component-design.md) when creating blueprint artifacts."`
    - Ensure agent-specific rules are renumbered sequentially after extraction.
- **MRP.xml Content:**
    - Common `<general_rules>`: State Transition Protocol, State Dashboard format, Sequential Action Workflow, Path & Link Formatting, Information Gathering Workflow, VCP, Standardized Plan Types, Code Block Formatting, Validation Failure Recovery, Conflict Resolution Protocol, Programmatic Edits, Template-First Documentation.
    - `<response_format>`: The shared MRP response format with a parameterized agent name placeholder (resolved at prompt assembly by the `Agent Name:` line injection).
    - State Dashboard template: A single shared format directive rather than per-agent repetition. Agents define their phase tracking in their specific workflow — the dashboard format itself is unified.
    - The agent name in the response format example metadata (`- **Agent:** {Agent Name}`) is not hardcoded; the agent infers it from the `Agent Name:` line at the top of the assembled prompt.
- **PromptManager Changes (`fetch_system_prompt`):**
    - Resolve agent-specific XML content as currently done.
    - Inject `Agent Name: {agent}\n` at the start of the assembled prompt.
    - Check if resolved content contains `<response_format>` (case-insensitive). If yes, return the resolved content as-is (legacy mode).
    - If not, append MRP.xml content loaded via `importlib.resources.files()`. Cache MRP.xml content per instance.
    - Raise `FileNotFoundError` if MRP.xml cannot be read.
    - Return the full assembled prompt string.

## Vertical Slices
- [x] **03-01-Editor-Validation-and-Discovery** — Editor discovery, early PATH validation, interactive selection prompt, persistence to config, "disabled" sentinel handling, and diff flags fallback for unknown editors. See the specification for full details.
- [ ] **03-02-MRP-Base-Prompt** — MRP.xml creation, PromptManager agent name + MRP injection logic, legacy detection, and removal of shared general_rules/response_format from agent XMLs. See the [slice definition](/docs/project/slices/03-02-mrp-base-prompt.md) for deliverables and scenarios.
- [ ] **03-03-Templates-and-Init** — Template files, `teddy init templates` subcommand, InitService changes, and blueprint removal from agent XMLs. See the [slice definition](/docs/project/slices/03-03-templates-and-init.md) for deliverables and scenarios.
