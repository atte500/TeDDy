# Slice: Templates and Init
- **Status:** Planned
- **Milestone:** [03-foundational-refactors](/docs/project/milestones/03-foundational-refactors.md)
- **Specs:** TBD (Milestone doc serves as spec)
- **Component Docs:** [InitService](/docs/architecture/core/services/init_service.md)
- **Scope Slug:** `templates-init`

## Business Goal
Eliminate redundant blueprint definitions across all 6 agent prompts by extracting shared content into centralized template files. Provide a `teddy init templates` command for users to regenerate project scaffolding in `docs/templates/`.

## Progress (Done vs To Do)

### Done (Content / Template Artifacts)
- [x] **Blueprints already removed from agent prompts.** All 6 agent XMLs (`architect`, `assistant`, `debugger`, `developer`, `pathfinder`, `prototyper`) no longer contain `<blueprints>` sections (verified: `git grep -l "<blueprints>"` returns nothing). The shared `<general_rules>`/`<response_format>` were likewise removed and now live in `MRP.xml` (slice 03-02).
- [x] **Bundled template folder already created** at `src/teddy_executor/resources/templates/`. It currently holds 10 Markdown templates:
    - `specification-document.md`, `component-design.md`, `ARCHITECTURE.md`, `PROJECT.md`, `makefile.md`, `ci.md`
    - `milestone.md`, `vertical-slice.md`, `case-file.md`, `task-brief.md`
- [x] This bundled folder is the source that `teddy init templates` will copy into a user project's `docs/templates/`. Template filenames follow the artifact-type convention (`milestone.md`, `vertical-slice.md`, `case-file.md`, `task-brief.md`) per MRP rule 12 — NOT the `MM-NN` instance-naming convention used for actual slice/case-file documents.

### To Do (Harness Code)
- [ ] Add `ensure_templates_initialized(overwrite=False) -> str` to the `IInitUseCase` ABC (additive member).
- [ ] Implement `InitService._init_templates()` + `ensure_templates_initialized()` following the existing `_init_prompts()` pattern; add a `templates_dir` constructor parameter.
- [ ] Add the `teddy init templates` CLI subcommand (calls `ensure_templates_initialized(overwrite=True)`).
- [ ] Bare `teddy init` also creates `docs/templates/`; `teddy start`/`teddy resume` auto-create it non-destructively.
- [ ] Add inline template directives in the agent XMLs (the replacement for the removed blueprints).
- [ ] Tests: template copy, partial-population non-destructiveness, and the CLI subcommand.

## Scenarios

> As a user, I want to run `teddy init templates` so that my project's `docs/templates/` directory is populated with default Markdown templates for all artifact types.

```gherkin
Given I have a project without a docs/templates/ directory
When I run `teddy init templates`
Then docs/templates/ is created
And it contains specification-document.md
And it contains task-brief.md
And it contains case-file.md
And it contains vertical-slice.md
And it contains milestone.md
And it contains component-design.md
And it contains ARCHITECTURE.md
And it contains PROJECT.md
And it contains makefile.md
And the PROJECT.md template references docs/templates/makefile.md as part of Milestone 0 foundational tasks
```

> As a user, I want to run `teddy init` (bare) so that docs/templates/ is also created on first initialization.

```gherkin
Given I have a project without a .teddy/ directory and without docs/templates/
When I run `teddy init` (without subcommand)
Then .teddy/ is created
And docs/templates/ is created
And it contains the expected template files
```

> As a user, I want the agent XMLs to reference templates from docs/templates/ instead of inline blueprints so that blueprint changes are a single-point update.

```gherkin
Given I inspect any agent XML prompt (e.g., architect.xml, developer.xml)
When I search for "<blueprints>" sections
Then no agent XML contains a <blueprints> section
And each agent XML contains appropriate inline directives referencing template files in docs/templates/
```

> As a user, I want short-lived test projects to have access to the Project Roadmap template even if docs/project/PROJECT.md doesn't exist yet, so that new projects can bootstrap their roadmap.

```gherkin
Given I have a new project without docs/project/PROJECT.md
And I run `teddy init templates`
When I read docs/templates/PROJECT.md
Then it contains a note or link referencing docs/templates/makefile.md as part of Milestone 0 foundational tasks
And it is usable as a standalone scaffold if the real PROJECT.md does not yet exist
```

## Edge Cases
- **Missing templates resource directory**: If `src/teddy_executor/resources/templates/` is missing from the package, `_init_templates()` should silently return "unchanged" without crashing. This matches the existing pattern for missing prompts/config.
- **docs/templates/ partially populated**: If some template files exist but others are missing, `ensure_templates_initialized(overwrite=False)` should only create missing files (non-destructive). With `overwrite=True`, all files are replaced.
- **`teddy init templates` in non-project directory**: Should create `docs/templates/` relative to CWD. Matches existing behavior of `teddy init`.

## Key Unknowns
All technical unknowns have been resolved during the Architectural Design phase. No prototyping needed.

- [x] [Technical] Template location strategy: Bundled in `src/teddy_executor/resources/templates/`, copied to `docs/templates/` during init.
- [x] [Functional] PROJECT.md template behavior: References `docs/templates/makefile.md` as part of Milestone 0 foundational tasks.
- [x] [Technical] InitService template loading pattern: Follows existing `_init_prompts()` pattern with a `templates_dir` constructor parameter.

## Implementation Plan

### Overview
This slice covers three tightly-coupled workstreams: (1) creating bundled template files, (2) adding `teddy init templates` CLI command, and (3) removing `<blueprints>` from agent XMLs. These are coupled because the blueprint removal depends on the templates existing as their replacement.

### Detailed Tech Strategy

#### InitService Template Path
InitService needs to load from `src/teddy_executor/resources/templates/`. This requires adding a second resource path alongside the existing `_config_dir`. Option A: Add a `_templates_dir` parameter. Option B: Use `importlib.resources` directly inside `_init_templates()`. **Recommendation: Option A** — it follows the existing pattern and allows test injection of a mock path.

#### Agent XML Modifications
Each of the 6 XMLs needs the same changes:
1. Remove the entire `<blueprints>` section (including opening/closing tags and all blueprint definitions).
2. Add a brief inline directive in the workflow instructions referencing `docs/templates/`.

### Deliverables
- [ ] **Contract** - Add `ensure_templates_initialized(overwrite=False) -> str` to `IInitUseCase` ABC.
- [x] **Contract** - The `src/teddy_executor/resources/templates/` directory exists with 10 bundled Markdown template files: `specification-document.md`, `task-brief.md`, `case-file.md`, `vertical-slice.md`, `milestone.md`, `component-design.md`, `ARCHITECTURE.md`, `PROJECT.md`, `makefile.md`, `ci.md`.
- [ ] **Harness** - Add test fixture support for InitService mock templates directory (follows existing `mock_fs` patterns in `test_init_service.py`).
- [ ] **Logic** - Implement `_init_templates()` and `ensure_templates_initialized()` in `InitService` following the existing `_init_prompts()` pattern.
- [ ] **Wiring** - Add `init_app.command("templates")` to `__main__.py` calling `ensure_templates_initialized(overwrite=True)`.
- [ ] **Wiring** - Modify `init_callback` in `__main__.py` to also call `ensure_templates_initialized()` when no subcommand is invoked.
- [ ] **Harness** - Add test for CLI `init templates` subcommand via CliRunner (verify command exists and produces correct output).
- [ ] **Refactor** - Update InitService constructor to accept optional `templates_dir` parameter (defaulting to `resources.files("teddy_executor.resources.templates")`).
- [ ] **Cleanup** - Remove `<blueprints>` sections from all 6 agent XMLs. Replace with inline template directive comments.

## Implementation Notes
- **Auto-init on startup:** `teddy start` and `teddy resume` automatically call `ensure_templates_initialized(overwrite=False)` to create `docs/templates/` if the directory is missing. This is non-destructive — existing template files are never overwritten. Only the explicit `teddy init templates` command uses `overwrite=True` to force-regenerate all templates from defaults. This behavior was decided during development to prevent agents from failing when template files are accidentally deleted, without risking overriding user-customized templates.

## Verification
1. [ ] Run `pytest tests/suites/unit/core/services/test_init_service.py -v` — all existing tests pass, new template tests pass.
2. [ ] Run `pytest tests/suites/unit/core/ports/inbound/test_init.py -v` — contract tests for new ABC method pass.
3. [ ] Run full test suite: `pytest` — all tests pass (green-to-green).
4. [ ] Manual: `cd /tmp/test-project && teddy init && ls docs/templates/` — confirms 10 template files exist.
5. [ ] Manual: `cd /tmp/test-project && cat docs/templates/PROJECT.md` — confirms link to `docs/project/PROJECT.md`.
6. [ ] Manual: `cd /tmp/test-project && rm -rf docs/templates/ && teddy init templates && ls docs/templates/` — confirms regeneration works.
7. [ ] Manual: `cat src/teddy_executor/resources/config/prompts/architect.xml | grep -c "<blueprints>"` — returns 0 (blueprints extracted to templates).
8. [ ] Manual: `cat src/teddy_executor/resources/config/prompts/architect.xml | grep -c "template"` — returns at least 1 (directive references templates).
