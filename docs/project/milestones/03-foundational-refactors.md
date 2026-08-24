# Milestone 3: Foundational Refactors

- **Status:** Planned
- **Specs:** TBD

## Goal (The "Why")
Eliminate redundant blueprint definitions across all 6 agent prompts by extracting shared content into `docs/templates/`, and reduce prompt maintenance burden by injecting the Markdown Response Protocol (MRP) and common general rules from a central `MRP.xml` base prompt. This decouples shared template definitions from agent-specific instructions, making maintenance simpler and changes single-point updates.

## Proposed Solution (The "What")
Three workstreams will be executed:

1. **Blueprint Extraction to docs/templates/:** Remove all `<blueprints>` sections from every agent XML prompt. Replace them with a directive in each agent's workflow instructions to reference the corresponding template from `docs/templates/` when creating an artifact. Create `docs/templates/` with default Markdown templates. Add `teddy init templates` subcommand. This requires zero architecture changes to the Prompt Manager — purely content changes to prompt XMLs and a file generation change to InitService.

2. **MRP.xml Base Prompt:** Extract the MRP response format and the common general rules (rules 1-9: State Transition Protocol, State Dashboard, Sequential Action Workflow, Path & Link Formatting, Information Gathering Workflow, VCP, Standardized Plan Types, Code Block Formatting, Validation Failure Recovery; plus Conflict Resolution and Programmatic Edits) that are duplicated identically across all 6 agents. Place these in `MRP.xml` as a base prompt. The Prompt Manager appends `MRP.xml` after the agent-specific XML at system prompt assembly time. `MRP.xml` is NOT copied to `.teddy/prompts/` for user modification.

3. **Makefile Template (docs/templates/makefile.md):** Create a Makefile template defining executable commands for the VCP commit workflow and the Debugger's Remote Probing Protocol. Defines `make commit 'message'` for the VCP workflow (stages, pre-commit runs, commits, and pushes) and `make probe 'reason'` for the Remote Probing Protocol (pushes probe, triggers CI workflow, retrieves logs). This serves as the specification for Milestone 0 bootstrapping — teams implement their project-specific Makefile following this pattern.

## Guidelines (The "How")
- **Test Harness Strategy:**
    - **Blueprint Extraction:** Verify via file system assertion that `docs/templates/` contains the expected template files after `teddy init` and `teddy init templates`. Verify agent XMLs no longer contain `<blueprints>` sections.
    - **MRP.xml Injection:** Verify via unit test of the PromptManager that the assembled prompt contains MRP content followed by agent-specific content. Verify `MRP.xml` is NOT present in `.teddy/prompts/` after init.
    - **init templates Subcommand:** Verify the subcommand exists in the CLI and regenerates `docs/templates/` correctly.
- **Fail-Fast:** The PromptManager MUST fail if `MRP.xml` is missing from resources.
- **Poka-Yoke:** No agent XML should be committed without removing `<blueprints>` sections — a CI check should verify this.

## Technical Specifications
- **Prompt Resolution:** The PromptManager (or system prompt assembler) currently reads agent XML files individually. For MRP.xml injection, the assembler MUST read `MRP.xml` from resources (not from `.teddy/prompts/`) and append its content after the agent-specific XML content before sending to the LLM.
- **File Locations:**
    - `docs/templates/specification-document.md` — Template for Specification Documents
    - `docs/templates/task-brief.md` — Template for Task Briefs
    - `docs/templates/case-file.md` — Template for Case Files
    - `docs/templates/vertical-slice.md` — Template for Vertical Slices
    - `docs/templates/milestone.md` — Template for Milestone documents
    - `docs/templates/component-design.md` — Template for Component Design Documents
    - `docs/templates/architecture-conventions.md` — Template for ARCHITECTURE.md Conventions section
    - `docs/templates/roadmap.md` — Template for PROJECT.md Roadmap section
    - `docs/templates/makefile.md` — Makefile template for VCP commit and Remote Probing Protocol commands
    - `src/teddy_executor/resources/MRP.xml` — Base prompt (NOT in docs/templates/ or .teddy/prompts/)
- **CLI Changes:** Add `teddy init templates` subcommand to the `init` command group.

## Vertical Slices
> Slice definitions will be created by the Architect during the Design phase. The following high-level breakdown is anticipated:
>
> 1. Blueprint extraction to `docs/templates/` + remove `<blueprints>` from agent XMLs + add workflow directives
> 2. MRP.xml creation + PromptManager injection logic
> 3. `makefile.md` template creation + `teddy init templates` subcommand
> 4. CI check enforcement (no `<blueprints>` in agent XMLs)
