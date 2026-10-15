# Slice: Prompt XML→Markdown Migration
- **Status:** Planned
- **Milestone:** Ad-hoc (not tracked in the Roadmap per PROJECT.md)
- **Specs:** [interactive-session-workflow](/docs/project/specs/interactive-session-workflow.md), [teddy-directory-structure](/docs/project/specs/teddy-directory-structure.md)
- **Prototype:** N/A (no unresolved technical/functional unknown)
- **Component Docs:** [PromptManager](/docs/architecture/core/services/prompt_manager.md), [InitService](/docs/architecture/core/services/init_service.md)
- **Scope Slug:** `prompt-md-migration`

## Business Goal
Migrate all 6 agent prompts and the shared MRP base prompt from XML to Markdown so the prompt files use the same Markdown format as the rest of the interface. Make `teddy init prompts` and the drift check treat a `.xml` and a `.md` file with the same stem as the SAME logical file, replacing a stale `.xml` with the new `.md` instead of leaving both side by side. When both extensions coexist, prompt resolution MUST deterministically prefer `.md`, and each agent prompt MUST start with its own `# {AgentName}` H1 as the source of the agent name.

## Scenarios

> As a user, I want my agent prompts to be Markdown files so they match the rest of the interface and are easier to read and edit.

```gherkin
Given the TeDDy package is installed
When I inspect src/teddy_executor/resources/config/prompts/
Then it contains architect.md, assistant.md, debugger.md, developer.md, pathfinder.md, and prototyper.md
And it contains no *.xml prompt files
And src/teddy_executor/resources/ contains MRP.md and no MRP.xml
```

> As a user upgrading from an XML prompt set, I want `teddy init prompts` to replace my old `.xml` prompts with the new `.md` prompts so I do not end up with two files for the same agent.

```gherkin
Given .teddy/prompts/ contains pathfinder.xml (an old XML prompt)
When I run `teddy init prompts`
Then .teddy/prompts/pathfinder.md is written
And .teddy/prompts/pathfinder.xml is removed
And only one file with the stem "pathfinder" remains
```

> As a user, I want non-destructive init to treat a same-stem file as already present so it does not create a duplicate.

```gherkin
Given .teddy/prompts/ contains pathfinder.xml and no pathfinder.md
When init runs non-destructively (overwrite=False)
Then .teddy/prompts/pathfinder.md is NOT created
And .teddy/prompts/pathfinder.xml is left in place
```

> As a user, I want the MRP base prompt to load from the Markdown resource so the assembled system prompt keeps working.

```gherkin
Given MRP.md is present in src/teddy_executor/resources/
When fetch_system_prompt() assembles a prompt
Then the Markdown MRP content is appended after the agent-specific content
And a missing MRP.md raises FileNotFoundError
```

> As a user, I want the drift check to recognize a same-stem file as present so it does not falsely report my prompts as missing.

```gherkin
Given .teddy/prompts/ contains pathfinder.xml (old extension)
When the drift check runs
Then "pathfinder" is NOT reported as missing
And it is reported as edited when its content differs from the bundled default
```

> As a user, I want a `.md` prompt to win over a stale `.xml` so my Markdown prompt is always the one that loads.

```gherkin
Given .teddy/prompts/ contains both pathfinder.xml and pathfinder.md
When the prompt is resolved
Then the pathfinder.md content is returned regardless of directory listing order
```

## Edge Cases
- **Same-stem collision on overwrite**: When `overwrite=True` and both `pathfinder.xml` and `pathfinder.md` exist, the `.md` is written and the `.xml` is removed, leaving exactly one file.
- **`.md`-priority resolution**: When a stem has both a `.md` and a `.xml` (or any other extension), the resolver returns the `.md` content regardless of directory listing order, so a pre-authored `.md` always wins over a stale `.xml`.
- **Legacy `<response_format>` override**: A pre-migration user override (`.xml` containing `<response_format>`) MUST still skip the MRP append. No Markdown marker is added: the Markdown MRP has never shipped, so there is nothing to detect.
- **Agent name from H1**: Each agent prompt starts with `# {AgentName}`; the `Agent Name: {Name}` header injection is removed and the agent name for the MRP `- **Agent:**` field is read from that H1.
- **Non-overwrite with only `.xml` present**: Treated as "already present" (same stem) → no `.md` written; the user keeps a working `.xml` until they explicitly re-init.
- **Session-persisted prompts**: Session-root prompt files derive their filename from the resolved `.teddy/prompts/` file (stem-based, `.md`-preferring), so after migration new sessions persist `{agent}.md`. Existing session tests seed their own `.xml` and continue to pass (resolution is extension-agnostic); they are intentionally left unchanged.
- **Bundled MRP missing**: `FileNotFoundError` (fail-fast) is preserved unchanged; only the filename changes.

## Key Unknowns

**Taxonomy:** see template.

- [x] [Domain] Markdown conversion convention for agent prompts and MRP: RESOLVED BY DECISION (see Implementation Notes). Design Sensitivity: if the convention is rejected, only file CONTENT changes — no code contract is affected.
- [x] [Technical] MRP loading with a `.md` filename: trivially supported — `_load_mrp_base_prompt` uses the `Traversable` contract (`is_file` + `read_text`) and is extension-agnostic. No spike needed.

## Scope & Impact
- `[MIGRATE]` `src/teddy_executor/resources/MRP.xml` → `MRP.md` — content converted; `PromptManager._MRP_FILENAME` updated.
- `[MIGRATE]` `src/teddy_executor/resources/config/prompts/*.xml` → `*.md` — 6 files converted; `InitService._PROMPT_FILES` updated.
- `[EXPAND]` `InitService._copy_bundled_files` / `_init_prompts` — add stem-identity matching so a same-stem file with a different extension is the same logical file (and is replaced on overwrite).
- `[EXPAND]` `InitService.check_drift` / `_classify_drift` — stem-identity existence matching for prompts.
- `[EXPAND]` `PromptManager._find_prompt_file` / `prompts._search_prompt_in_dir` / `SessionService._resolve_agent_prompt` — prefer `.md` over any other extension for a shared stem.
- `[EXPAND]` `PromptManager._assemble_composed_prompt` — remove the `Agent Name: {Name}` header injection (the agent name now comes from the prompt's `# {AgentName}` H1); keep the `<response_format>` short-circuit unchanged.
- `[CONTRACT]` none (no port signatures change).
- `[MIGRATE]` tests + docs enumerated in the deliverables below.

## Deliverables
Ordering follows `docs/templates/vertical-slice.md`. There is NO `Wiring` deliverable: this migration introduces no new boundary — it reuses the existing `PromptManager`/`InitService` seams. Deliverable 1 is the thinnest end-to-end tracer bullet (MRP file + constant + tests).

- [ ] **Logic** — MRP base prompt migration (tracer bullet): create `src/teddy_executor/resources/MRP.md` with the converted content (same general rules + response format, Markdown structure, first line `# Markdown Response Protocol (MRP)`); set `PromptManager._MRP_FILENAME = "MRP.md"`; keep the `<response_format>` short-circuit in `_assemble_composed_prompt` (NO Markdown marker); remove the `Agent Name: {Name}` header injection and read the agent name from the prompt's `# {AgentName}` H1; delete `src/teddy_executor/resources/MRP.xml`. Update `tests/suites/unit/core/services/test_prompt_manager.py` (MRP fixture filename + header-injection assertions) and `tests/suites/unit/core/services/test_bug_03_prompt_resolution.py`; audit `tests/suites/acceptance/test_mrp_prompt_assembly.py` for XML-content assertions and update them to the Markdown MRP content.
- [ ] **Logic** — Agent prompt migration + stem-identity init + `.md`-priority resolution: create the 6 `*.md` agent prompts (each starting with `# {AgentName}`); set `InitService._PROMPT_FILES` to the `.md` names; add stem-identity matching to the prompt copy path so a same-stem different-extension file is treated as present and, on `overwrite=True`, is replaced (the stale `.xml` is removed); update `check_drift`/`_classify_drift` to match prompts by stem; make `PromptManager._find_prompt_file`, `prompts._search_prompt_in_dir`, and `SessionService._resolve_agent_prompt` prefer `.md` when a stem has both extensions; delete the 6 `*.xml` agent prompts. Update `tests/suites/unit/core/services/test_init_service.py`, `tests/suites/unit/core/services/test_init_service_drift.py`, `tests/suites/unit/test_init_cli_regression.py`, `tests/suites/unit/test_prompt_resource_relocation.py`. Unit tests MUST cover: overwrite replaces `.xml` with `.md` (exactly one file remains); non-overwrite skips when only a same-stem `.xml` exists; drift does not report a same-stem file as missing; the resolver returns `.md` when both extensions exist.
- [ ] **Cleanup** — Docs + residual references: update `README.md` (init prompts + command reference: "prompt XMLs" → Markdown prompt files), `docs/architecture/ARCHITECTURE.md` ("Prompt Files Are Plaintext" bullet and Prompt Assembly §5: `*.xml`/`MRP.xml` → `*.md`/`MRP.md`, plus the removed header-injection step), `docs/architecture/core/services/prompt_manager.md` (MRP path/filename + `*.xml` → `*.md` + H1 header semantics), `docs/architecture/core/services/init_service.md` (stem-identity copy/drift semantics), `docs/project/specs/interactive-session-workflow.md` (`MRP.xml`, `{agent_name}.xml`), and `docs/project/specs/teddy-directory-structure.md` (`system_prompt.xml`, `{agent_name}.xml`). Run `git grep -nF ".xml" -- src` and confirm no prompt/MRP `.xml` reference remains. Leave completed Milestone 3 history in `docs/project/PROJECT.md` unchanged (historical record).

## Implementation Notes
- **No Wiring deliverable.** The migration reuses the existing `PromptManager`/`InitService` seams; no new boundary is introduced.
- **Pre-authored content.** The 7 Markdown content files (`MRP.md` + the 6 agent prompts) are authored by Pathfinder as non-behavioral content and committed locally (not pushed) BEFORE the Developer starts. They are inert until the Developer repoints the constants and deletes the `.xml` originals; the repo stays green in between because nothing resolves from the bundled resource directory at runtime.
- **Agent-name source (no header injection).** Each agent prompt starts with its own `# {AgentName}` H1 (e.g. `# Pathfinder`). The `Agent Name: {Name}` header injection is REMOVED from `_assemble_composed_prompt`; the agent name for the MRP `- **Agent:**` metadata field is read from that H1.
- **Conversion convention (agent prompts):** top-level element → `# {AgentName}`; `persona` → `## Persona`; the `workflow` → `## Workflow` preceded by a one-line intro (`Follow these phases and steps in order. Keep track of your progress in your State Dashboard.`); each `phase n="X" name="Y"` → an unnumbered heading `### Y`; `goal` → a bold label line with the description on the same line (`**Goal:** …`); each `step n="X" name="Y"` → a numbered list item whose bolded title sits alone on its line with the description indented on the next line (`N. **Y:**` then an indented description), with multi-paragraph or nested sub-content (sub-lists, continuation paragraphs) indented under the item. Preserve all prose, inline code, and code fences verbatim. Remove the XML wrapper tags only.
- **Conversion convention (MRP):** `mrp` → `# Markdown Response Protocol (MRP)`; `general_rules` → `## General Rules`; `rule n="X" name="Y"` → `### Rule X: Y`; `state name="Z"` → `#### Z`; `response_format` → `## Response Format` with nested `###`/`####` for the constraint/action formats. Update the `- **Agent:**` guidance to reference the agent prompt's H1.
- **Stem-identity semantics (init):** a file is "present" when any file in the destination directory shares its stem (case-folded). On `overwrite=True`, the target `.md` is written and any same-stem file with a different name is removed, so two same-stem files never coexist after a write. Non-prompt copies (config, templates) keep exact-name matching (their extensions never change).
- **Stem-priority resolution (`.md` wins):** when a stem has both a `.md` and a `.xml` (or any other extension), the resolver returns the `.md` content regardless of directory listing order. Applies to `PromptManager._find_prompt_file`, `prompts._search_prompt_in_dir`, and `SessionService._resolve_agent_prompt`.
- **Legacy detection:** keep ONLY `<response_format>` for pre-migration XML overrides. No Markdown MRP marker is added (the Markdown MRP has never shipped).
- **Session-prompt filename coupling:** `SessionService._resolve_agent_prompt` returns the actual `.teddy/prompts/` filename, so new sessions persist `{agent}.md` automatically. The `test_session_service*` suites seed their own `.xml` files and are intentionally out of scope (resolution is extension-agnostic and `.md`-preferring).

## Verification
- [ ] Run `make test` and verify the full suite passes (green-to-green).
- [ ] Run `git grep -nF ".xml" -- src/teddy_executor/resources` and verify it returns nothing.
- [ ] Run `ls src/teddy_executor/resources/config/prompts/` and verify 6 `.md` files and no `.xml` files.
- [ ] Run `teddy get-prompt pathfinder` and verify the output starts with `# Pathfinder` and contains the Markdown MRP.
- [ ] In a temp project with both `.teddy/prompts/pathfinder.xml` and `.teddy/prompts/pathfinder.md`, run `teddy get-prompt pathfinder` and verify the `.md` content is returned (`.md` wins).
- [ ] In a temp project with `.teddy/prompts/pathfinder.xml` present, run `teddy init prompts` and verify `pathfinder.md` exists and `pathfinder.xml` is gone.
- [ ] In a temp project with only `.teddy/prompts/pathfinder.xml`, run bare `teddy init` and verify no `pathfinder.md` is created (same-stem = present).
- [ ] Run `teddy init templates` and verify templates are unaffected.
