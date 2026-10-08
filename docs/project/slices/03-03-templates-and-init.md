# Slice: Templates and Init
- **Status:** In Progress
- **Milestone:** [03-foundational-refactors](/docs/project/milestones/03-foundational-refactors.md)
- **Specs:** TBD (Milestone doc serves as spec)
- **Component Docs:** [InitService](/docs/architecture/core/services/init_service.md)
- **Scope Slug:** `templates-init`

## Business Goal
Eliminate redundant blueprint definitions across all 6 agent prompts by extracting shared content into centralized template files. Provide a `teddy init templates` command for users to regenerate project scaffolding in `docs/templates/`.

## Progress (Done vs To Do)

### Done (Content / Template Artifacts)
- [x] **Blueprints already removed from agent prompts.** All 6 agent XMLs (`architect`, `assistant`, `debugger`, `developer`, `pathfinder`, `prototyper`) no longer contain `<blueprints>` sections (verified: `git grep -l "<blueprints>"` returns nothing). The shared `<general_rules>`/`<response_format>` were likewise removed and now live in `MRP.xml` (slice 03-02).
- [x] **Bundled template folder already created** at `src/teddy_executor/resources/templates/`. It currently holds 11 Markdown templates:
    - `specification-document.md`, `component-design.md`, `ARCHITECTURE.md`, `PROJECT.md`, `makefile.md`, `ci.md`, `pre-commit.md`
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

## Deliverables
- [x] **Contract** - The `src/teddy_executor/resources/templates/` directory exists with 11 bundled Markdown template files: `specification-document.md`, `task-brief.md`, `case-file.md`, `vertical-slice.md`, `milestone.md`, `component-design.md`, `ARCHITECTURE.md`, `PROJECT.md`, `makefile.md`, `ci.md`, `pre-commit.md`.
- [x] **Logic** - Implement template support in `InitService`: add an optional `templates_dir` constructor parameter (defaulting to `resources.files("teddy_executor.resources") / "templates"`), add `_init_templates(overwrite=False) -> str` copying the 11 bundled templates into `docs/templates/` (non-destructive unless `overwrite=True`), and add `ensure_templates_initialized(overwrite=False) -> str`. Unit tests cover: full copy, partial-population non-destructiveness, `overwrite=True` replacement, and missing-resource no-op.
- [x] **Contract** - Add `ensure_templates_initialized(overwrite: bool = False) -> str` as an additive abstract member of the `IInitUseCase` ABC, plus a contract test at `tests/suites/unit/core/ports/inbound/test_init.py`. Declared AFTER `InitService` implements it to preserve green-to-green.
- [x] **Wiring** - Extend `InitService.ensure_initialized()` to also call `_init_templates(overwrite=False)` and fold the templates status into its summary string, so bare `teddy init`, `teddy start`, and `teddy resume` auto-create `docs/templates/` non-destructively. Update the two exact-string summary tests in `test_init_service.py`.
- [ ] **Wiring** - Add the `teddy init templates` subcommand to `__main__.py` (calls `ensure_templates_initialized(overwrite=True)`); add an acceptance test via `CliRunner` proving the command exists and populates `docs/templates/`.
- [ ] **Cleanup** - Add inline `docs/templates/` directives to the 5 agent XMLs that still lack them (`architect`, `assistant`, `developer`, `pathfinder`, `prototyper`); `debugger.xml` already carries them. Confirm no `<blueprints>` remain anywhere.

## Implementation Notes
- **Auto-init on startup:** `teddy start` and `teddy resume` automatically create `docs/templates/` (non-destructively) because `_ensure_project_initialized()` calls `InitService.ensure_initialized()`, which folds in `_init_templates(overwrite=False)`. Existing template files are never overwritten; only the explicit `teddy init templates` command uses `overwrite=True` to force-regenerate all templates from defaults. This prevents agents from failing when template files are accidentally deleted, without risking overriding user-customized templates.
- **Deliverable ordering (re-partitioned during Plan Audit):** The original plan placed the `Contract` (adding the abstract `ensure_templates_initialized` to `IInitUseCase`) before the `Logic` (the concrete `InitService` implementation). Because `IInitUseCase` is a shared seam and `InitService` is its only concrete implementation, adding the abstract member first would make `InitService` uninstantiable (`TypeError: Can't instantiate abstract class InitService with abstract method ensure_templates_initialized`) and turn the suite red — a non-green break. The plan was re-ordered to implement the concrete method first (`Logic`), then declare it on the ABC (`Contract`), preserving a green-to-green transition at every step.
- **Template count correction:** The bundled `src/teddy_executor/resources/templates/` directory holds **11** files, not 10 as originally scoped. The extra file is `pre-commit.md`.
- **Logic deliverable (InitService template support) - implementation:** Added an optional `templates_dir` constructor parameter, `_init_templates(overwrite=False) -> str`, and `ensure_templates_initialized(overwrite=False) -> str`. The default `templates_dir` resolves via `importlib.resources.files("teddy_executor.resources") / "templates"` (joined onto the `resources` package rather than resolving a `resources.templates` subpackage, so the bundled directory needs no `__init__.py`). Three file-scoped refactors were folded into this deliverable: `_read_bundled_resource` (shared resource read used by both config and templates), `_format_init_status` (single-sources the "unchanged" / "updated (N files)" / "overwritten (N files)" vocabulary across config/prompts/templates), and `_copy_bundled_files` (one copy routine for the create-dir + conditional-write + count loop). The `_TEMPLATE_FILES` manifest is a module-level constant single-sourced with the unit test (no shadow literal). Unit coverage: full copy, partial-population non-destructiveness, `overwrite=True` replacement, missing-resource no-op, and the wrapper status string.
- **Contract deliverable (IInitUseCase Expansion) - implementation:** Declared `ensure_templates_initialized(overwrite: bool = False) -> str` as an additive `@abstractmethod` on the `IInitUseCase` ABC, placed after `ensure_config_initialized` to mirror `InitService`'s ordering. Contract test at `tests/suites/unit/core/ports/inbound/test_init.py` asserts both the abstract-member declaration and the `overwrite=False` default via `inspect.signature`. The ordering deliberately placed this Expansion AFTER the concrete `InitService` implementation: because `InitService` is the sole `IInitUseCase` implementer, declaring the member first would have made `InitService` uninstantiable and turned the suite red. The contract test lives in the Unit layer per layer isolation and does not import `InitService`.
- **Wiring deliverable (auto-init on bare `teddy init`) - implementation:** Extended `InitService.ensure_initialized()` to call `_init_templates(overwrite=False)` and fold a third `Templates:` segment into the returned summary, so bare `teddy init`, `teddy start`, and `teddy resume` all scaffold `docs/templates/` non-destructively. The acceptance-layer Tracer Bullet `tests/suites/acceptance/test_templates_auto_init.py` drives bare `teddy init` through the CLI and asserts all 11 bundled templates land in `docs/templates/`; its expected filenames are declared locally rather than imported from `InitService._TEMPLATE_FILES` to respect acceptance-layer import isolation. The two exact-string summary tests in `test_init_service.py` were updated in the same Green step for green-to-green — the `service` fixture sets no `templates_dir`, so its template resource resolves outside the mocked `/mock/config` tree and reports "unchanged" (truthful, not a bug). In the Refactor step, both `ensure_initialized` docstring examples (concrete service + `IInitUseCase`) were corrected from the stale two-segment form to the three-segment form.

## Verification
1. [ ] Run `pytest tests/suites/unit/core/services/test_init_service.py -v` — all existing tests pass, new template tests pass.
2. [ ] Run `pytest tests/suites/unit/core/ports/inbound/test_init.py -v` — contract tests for new ABC method pass.
3. [ ] Run full test suite: `pytest` — all tests pass (green-to-green).
4. [ ] Manual: `cd /tmp/test-project && teddy init && ls docs/templates/` — confirms 11 template files exist.
5. [ ] Manual: `cd /tmp/test-project && cat docs/templates/PROJECT.md` — confirms link to `docs/project/PROJECT.md`.
6. [ ] Manual: `cd /tmp/test-project && rm -rf docs/templates/ && teddy init templates && ls docs/templates/` — confirms regeneration works.
7. [ ] Manual: `cat src/teddy_executor/resources/config/prompts/architect.xml | grep -c "<blueprints>"` — returns 0 (blueprints extracted to templates).
8. [ ] Manual: `cat src/teddy_executor/resources/config/prompts/architect.xml | grep -c "template"` — returns at least 1 (directive references templates).
