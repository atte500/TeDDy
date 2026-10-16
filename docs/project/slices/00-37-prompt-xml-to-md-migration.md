# Slice: Prompt XML→Markdown Migration
- **Status:** Completed
- **Milestone:** Ad-hoc (not tracked in the Roadmap per PROJECT.md)
- **Specs:** [interactive-session-workflow](/docs/project/specs/interactive-session-workflow.md), [teddy-directory-structure](/docs/project/specs/teddy-directory-structure.md)
- **Prototype:** N/A (no unresolved technical/functional unknown)
- **Component Docs:** [PromptManager](/docs/architecture/core/services/prompt_manager.md), [InitService](/docs/architecture/core/services/init_service.md)
- **Scope Slug:** `prompt-md-migration`

## Business Goal
Migrate all 6 agent prompts and the shared MRP base prompt from XML to Markdown so the prompt files use the same Markdown format as the rest of the interface, and delete the obsolete bundled `.xml` files so the package ships Markdown prompts only. Make `teddy init prompts` treat a `.xml` and a `.md` file with the same stem as the SAME logical file, replacing a stale `.xml` with the new `.md` instead of leaving both side by side, and make the `teddy start` preflight drift check flag a stale `.xml` so the user is advised to refresh. When both extensions coexist, prompt resolution MUST deterministically prefer `.md`, and each agent prompt MUST start with its own `# {AgentName}` H1 as the source of the agent name. The composed system prompt MUST separate the agent prompt from the MRP base prompt with a Markdown horizontal rule (`---`) padded by a blank line above and below.

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

> As a user with old `.xml` prompts, I want `teddy start` to detect the discrepancy so I am advised to refresh my prompts.

```gherkin
Given .teddy/prompts/ contains pathfinder.xml (an old XML prompt)
When I run `teddy start`
Then the preflight drift notification advises `teddy init prompts`
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
- **Legacy `<response_format>` override**: A pre-migration user override (`.xml` containing `<response_format>`) MUST still skip the MRP append. No Markdown marker is added: the Markdown MRP has never shipped, so there is nothing to detect. Because no MRP block is appended, no `---` separator is inserted either.
- **Agent name from H1**: Each agent prompt starts with `# {AgentName}`; the `Agent Name: {Name}` header injection is removed and the agent name for the MRP `- **Agent:**` field is read from that H1.
- **Non-overwrite with only `.xml` present**: Treated as "already present" (same stem) → no `.md` written; the user keeps a working `.xml` until they explicitly re-init.
- **Stale `.xml` surfaced as drift**: after migration the prompt manifest is `.md`, so a user's old `pathfinder.xml` makes `pathfinder.md` report as drift and the `teddy start` preflight advises `teddy init prompts`. Running `teddy init prompts` replaces the `.xml` with the `.md`. (This slice originally reported the stale `.xml` as a missing `.md`; slice `00-38-stem-aware-prompt-drift` later made the drift check stem-aware, so the same file now reports as EDITED.)
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
- `[EXPAND]` `InitService._PROMPT_FILES` — repoint the prompt manifest to the `.md` names so a stale `.xml` surfaces as drift in the drift check (the `teddy start` preflight then advises `teddy init prompts`). At the time of this slice the check matched by exact name, so the stale `.xml` reported as a missing `.md`; slice `00-38-stem-aware-prompt-drift` later made the check stem-aware (a `_classify_drift` change), so the same file now reports as EDITED.
- `[EXPAND]` `PromptManager._find_prompt_file` / `prompts._search_prompt_in_dir` / `SessionService._resolve_agent_prompt` — prefer `.md` over any other extension for a shared stem.
- `[EXPAND]` `PromptManager._assemble_composed_prompt` — remove the `Agent Name: {Name}` header injection (the agent name now comes from the prompt's `# {AgentName}` H1); join the agent content and the appended MRP base prompt with a `---` horizontal rule padded by a blank line above and below; keep the `<response_format>` short-circuit unchanged (no separator is inserted when the MRP block is skipped).
- `[CONTRACT]` none (no port signatures change).
- `[MIGRATE]` tests + docs enumerated in the deliverables below.

## Deliverables
Ordering follows `docs/templates/vertical-slice.md`. There is NO `Wiring` deliverable: this migration introduces no new boundary — it reuses the existing `PromptManager`/`InitService` seams. Deliverable 1 is the thinnest end-to-end tracer bullet (MRP file + constant + tests).

- [x] **Logic** — MRP base prompt migration (tracer bullet): create `src/teddy_executor/resources/MRP.md` with the converted content (same general rules + response format, Markdown structure, first line `# Markdown Response Protocol`); set `PromptManager._MRP_FILENAME = "MRP.md"`; keep the `<response_format>` short-circuit in `_assemble_composed_prompt` (NO Markdown marker); remove the `Agent Name: {Name}` header injection and read the agent name from the prompt's `# {AgentName}` H1; join the agent content and the appended MRP base prompt with a `---` horizontal rule padded by a blank line above and below; delete `src/teddy_executor/resources/MRP.xml`. Update `tests/suites/unit/core/services/test_prompt_manager.py` (MRP fixture filename + header-injection assertions) and `tests/suites/unit/core/services/test_bug_03_prompt_resolution.py`; audit `tests/suites/acceptance/test_mrp_prompt_assembly.py` for XML-content assertions and update them to the Markdown MRP content, asserting the `---` separator sits between the agent content and the MRP block.
- [x] **Logic** — `.md`-priority prompt resolution: make `PromptManager._find_prompt_file`, `prompts._search_prompt_in_dir`, and `SessionService._resolve_agent_prompt` prefer `.md` over any other extension when a stem has multiple files, regardless of directory listing order. Add unit tests covering the "both extensions present → `.md` wins" case for all three resolvers. Existing `.xml`-only tests stay green (a single stem match still resolves).
- [x] **Logic** — Agent prompt migration + stem-identity init: repoint `InitService._PROMPT_FILES` to the `.md` names so the drift check reports a stale `.xml` as a missing `.md` (the `teddy start` preflight then advises `teddy init prompts`); add stem-identity matching to the prompt copy path so a same-stem different-extension file is treated as present and, on `overwrite=True`, is replaced (the stale `.xml` is removed); delete the 6 bundled `*.xml` agent prompts (the 6 pre-authored `*.md` prompts already exist and each starts with `# {AgentName}`). Update `tests/suites/unit/core/services/test_init_service.py`, `tests/suites/unit/core/services/test_init_service_drift.py`, `tests/suites/unit/test_init_cli_regression.py`, `tests/suites/unit/test_prompt_resource_relocation.py`, and refresh the stale "edited" comment in `tests/suites/acceptance/test_preflight_drift_notification.py`. Unit tests MUST cover: overwrite replaces `.xml` with `.md` (exactly one file remains); non-overwrite skips when only a same-stem `.xml` exists; the drift check reports a stale `.xml` as drift (so `teddy start` advises `teddy init prompts`).
- [x] **Cleanup** — Docs + residual references: update `README.md` (init prompts + command reference: "prompt XMLs" → Markdown prompt files), `docs/architecture/ARCHITECTURE.md` ("Prompt Files Are Plaintext" bullet and Prompt Assembly §5: `*.xml`/`MRP.xml` → `*.md`/`MRP.md`, plus the removed header-injection step), `docs/architecture/core/services/prompt_manager.md` (MRP path/filename + `*.xml` → `*.md` + H1 header semantics), `docs/architecture/core/services/init_service.md` (stem-identity copy/drift semantics), `docs/project/specs/interactive-session-workflow.md` (`MRP.xml`, `{agent_name}.xml`), and `docs/project/specs/teddy-directory-structure.md` (`system_prompt.xml`, `{agent_name}.xml`). Run `git grep -nF ".xml" -- src` and confirm no prompt/MRP `.xml` reference remains. Leave completed Milestone 3 history in `docs/project/PROJECT.md` unchanged (historical record).

- [x] **Cleanup** — Residual `src` docstrings/comments: update the non-behavioural prompt-migration wording the earlier `.xml`/`Agent Name` sweep missed — `__main__.py` (`init prompts` "bundled prompt XMLs"; `get-prompt` "agent-name header, the agent-specific XML"), `core/ports/outbound/prompt_manager.py` (`compose_system_prompt` "agent-name header + agent XML"), `core/ports/outbound/session_manager.py` ("prompt XML"), `core/services/prompt_manager.py` ("prompt XML from the canonical"), and `core/services/session_service.py` ("agent-name header + agent XML + MRP", "prompt XML"). Run `git grep -niF "xml" -- src` and confirm only the intentional `.md`-priority/stem-identity descriptions remain.

## Implementation Notes
- **No Wiring deliverable.** The migration reuses the existing `PromptManager`/`InitService` seams; no new boundary is introduced.
- **Pre-authored content.** The 7 Markdown content files (`MRP.md` + the 6 agent prompts) are authored by Pathfinder as non-behavioral content and committed locally (not pushed) BEFORE the Developer starts. They are inert until the Developer repoints the constants and deletes the `.xml` originals; the repo stays green in between because nothing resolves from the bundled resource directory at runtime.
- **Agent-name source (no header injection).** Each agent prompt starts with its own `# {AgentName}` H1 (e.g. `# Pathfinder`). The `Agent Name: {Name}` header injection is REMOVED from `_assemble_composed_prompt`; the agent name for the MRP `- **Agent:**` metadata field is read from that H1.
- **Agent/MRP separator.** `_assemble_composed_prompt` joins the agent content and the MRP base prompt with a Markdown horizontal rule (`---`) padded by a blank line above and below, so the composed prompt reads `{agent content}`, then a blank line, then `---`, then a blank line, then `{MRP content}`. The legacy `<response_format>` short-circuit returns the agent content WITHOUT a separator, because no MRP block is appended in that case.
- **Conversion convention (agent prompts):** top-level element → `# {AgentName}`; `persona` → `## Persona`; the `workflow` → `## Workflow` preceded by a one-line intro (`Follow these phases and steps in order. Keep track of your progress in your State Dashboard.`); each `phase n="X" name="Y"` → an unnumbered heading `### Y`; `goal` → a bold label line with the description on the same line (`**Goal:** …`); each `step n="X" name="Y"` → a numbered list item whose bolded title sits alone on its line with the description indented on the next line (`N. **Y:**` then an indented description), with multi-paragraph or nested sub-content (sub-lists, continuation paragraphs) indented under the item. Preserve all prose, inline code, and code fences verbatim. Remove the XML wrapper tags only.
- **Conversion convention (MRP):** `mrp` → `# Markdown Response Protocol` followed by an intro paragraph describing the document; `general_rules` → `## General Rules` with each `rule` rendered as an unnumbered `### Name`; `state name="Z"` → `#### Z`; `response_format` → `## Response Format` holding each `constraint` as an unnumbered `### Name`, followed by `### Structure`; a top-level `## Example` sits at the very end of the document; the action formats live under a top-level `## Available Actions`, each `action` rendered as a level-3 heading naming the action in backticks. The `- **Agent:**` guidance references the agent prompt's `# {AgentName}` H1. All fenced code blocks inside MRP use 6 backticks.
- **Stem-identity semantics (init):** a file is "present" when any file in the destination directory shares its stem (case-folded). On `overwrite=True`, the target `.md` is written and any same-stem file with a different name is removed, so two same-stem files never coexist after a write. Non-prompt copies (config, templates) keep exact-name matching (their extensions never change).
- **Drift detection for stale `.xml`:** the prompt manifest (`_PROMPT_FILES`) is the `.md` names, so a user's old `pathfinder.xml` makes `pathfinder.md` report as drift. The `teddy start` preflight then advises `teddy init prompts`, which (with `overwrite=True`) writes the `.md` and removes the stale `.xml`. At the time of this slice the drift check matched by exact name (so the stale `.xml` reported as a missing `.md`); slice `00-38-stem-aware-prompt-drift` later made the check stem-aware, so the same file now reports as EDITED.
- **Stem-priority resolution (`.md` wins):** when a stem has both a `.md` and a `.xml` (or any other extension), the resolver returns the `.md` content regardless of directory listing order. Applies to `PromptManager._find_prompt_file`, `prompts._search_prompt_in_dir`, and `SessionService._resolve_agent_prompt`.
- **Legacy detection:** keep ONLY `<response_format>` for pre-migration XML overrides. No Markdown MRP marker is added (the Markdown MRP has never shipped).
- **Session-prompt filename coupling:** `SessionService._resolve_agent_prompt` returns the actual `.teddy/prompts/` filename, so new sessions persist `{agent}.md` automatically. The `test_session_service*` suites seed their own `.xml` files and are intentionally out of scope (resolution is extension-agnostic and `.md`-preferring).

### Deliverable 1 — As-Built (MRP base prompt migration)
- **Constant repointed, file not created:** `PromptManager._MRP_FILENAME` is now `"MRP.md"`. The pre-authored `MRP.md` already existed, so this deliverable repointed the constant rather than creating the file. The obsolete bundled `MRP.xml` was deleted via `git rm`.
- **Assembly contract:** `_assemble_composed_prompt` now takes only `content` (the `agent_name` parameter was removed as it became unused). It returns `content` verbatim when the content carries `<response_format>` (legacy short-circuit; no separator), otherwise `f"{content}\n\n---\n\n{mrp}"`. Its two internal call sites were updated to the single-argument signature.
- **Header injection removed:** the `Agent Name: {Name}` prefix is gone; the now-unused `canonical_agent_name` import was dropped from `prompt_manager.py` (Ruff F401). The agent name is now read from the prompt's own `# {AgentName}` H1.
- **Test blast radius (wider than the slice listed):** the removed header was asserted in five files. Beyond the three the slice names, `tests/suites/acceptance/test_cli_ux_improvements.py` and `tests/suites/acceptance/test_pipeline_default_agent.py` also asserted `Agent Name:` and were updated to the new contract. Classified as a Local Flaw (in-scope test edits), not a Systemic Regression.
- **Pre-existing lint blocker cleared:** `tests/suites/unit/core/services/test_bug_03_prompt_resolution.py` already tripped Ruff TID251 (`MagicMock`/`patch`); its two lifecycle tests were rewritten with `Mock` + `monkeypatch.setattr`, making the file lint-clean so the pre-commit gate passes.
- **Integration gate:** `make test` reports the full suite green (1746 passed, 5 skipped).

### Deliverable 2 — Decomposition
Deliverable 2 was decomposed into two atomic deliverables during the Orientation audit because it bundled two independent logical changes: the resolver `.md`-preference (a pure, green-safe behavioral addition) and the init manifest repoint + stem-identity copy + bundled `.xml` deletion (a coupled trio that must land together — without the stem-identity copy, repointing the manifest to `.md` would make a non-overwrite run create a duplicate `.md` beside an existing `.xml`). The resolver preference lands first so its new test can be written in isolation against mocked filesystems; the init changes follow.

### Deliverable 2a — As-Built (`.md`-priority prompt resolution)
- **Single shared helper:** added `prefer_markdown(candidates)` to `src/teddy_executor/core/utils/paths.py` (a pure leaf module, now importing `Path` and `typing` alongside `re`). It returns the first candidate whose suffix case-folds to `.md`, else the first candidate, else `None` for an empty iterable. The `.md` suffix is a module constant (`_MARKDOWN_SUFFIX`).
- **Three call sites wired:** `prompts._search_prompt_in_dir`, `PromptManager._find_prompt_file`, and `SessionService._resolve_agent_prompt` each now collect ALL same-stem matches and delegate the choice to `prefer_markdown`, replacing the previous first-match loop/`break`. The "no `.md`" path stays byte-for-byte (first candidate), so `.xml`-only resolution is unchanged.
- **New coverage:** `tests/suites/unit/test_prompts.py::test_find_prompt_content_prefers_md_over_xml`; `tests/suites/unit/core/services/test_prompt_manager.py::test_find_prompt_file_prefers_md_when_stem_has_both_extensions`; and the new file `tests/suites/unit/core/services/test_session_service_prompt_resolution.py::test_resolve_agent_prompt_prefers_md_over_xml`. Each lists the `.xml` first so a naive first-match would deterministically return it.
- **Import direction:** `paths.py` is a leaf, so importing it into the top-level `prompts.py` and the core services introduces no cycle.
- **Integration gate:** `make test` reports the full suite green (1749 passed, 5 skipped).

### Deliverable 2b — Orientation Audit
- **Shared-seam check:** `_copy_bundled_files` has 3 call sites (config, prompts, templates); the new stem-identity behaviour is added as a defaulted parameter, so it is a non-breaking extension. `_PROMPT_FILES` has 2 consumers (`_init_prompts`, `check_drift`); repointing it to the `.md` names is a data change internal to this deliverable.
- **Deletion capability:** `IFileSystemManager.remove_file(path)` exists, so a stale same-stem `.xml` can be removed on `overwrite=True`.
- **No further decomposition:** the manifest repoint, the stem-identity copy, and the bundled `.xml` deletion are mutually dependent (each requires the prior) and land together.

### Deliverable 2b — As-Built (agent prompt migration + stem-identity init)
- **Manifest repointed:** `InitService._PROMPT_FILES` now lists the six `.md` names, so the drift check reports a user's stale `pathfinder.xml` as drift. At the time of this slice the check matched by exact name (a stale `.xml` classified as a missing `.md`); slice `00-38-stem-aware-prompt-drift` later made the check stem-aware, so the same file now reports as EDITED.
- **Stem-identity copy:** `_copy_bundled_files` gained a defaulted `stem_identity: bool = False` parameter plus two helpers — `_stem_key` (case-folded `Path(...).stem`) and `_prune_same_stem` (removes any same-stem file with a different name after a write). When `stem_identity` is set, a destination entry sharing an entry's stem under ANY extension counts as present; on `overwrite=True` the target `.md` is written and the stale same-stem file is removed. Only `_init_prompts` passes `stem_identity=True`; the config and template copies keep exact-name matching.
- **Bundled `.xml` deleted:** the six obsolete agent prompts were removed via `git rm`, leaving the six pre-authored `.md` prompts as the only files under `resources/config/prompts/`.
- **Import added:** `init_service.py` now imports `pathlib.Path` for the stem helpers.
- **Test blast radius:** `test_init_service.py` (local `PROMPT_FILES` literal and the existing prompt-copy assertion moved to `.md`), `test_init_service_drift.py` (edited-prompt fixture/assertion moved to `.md`), `test_init_cli_regression.py` (workspace seeded with the `.md` prompt set), `test_prompt_resource_relocation.py` (manifest + docstring moved to `.md`), plus a stale-comment refresh in `test_preflight_drift_notification.py`. The four Red tests added earlier now pass.
- **Integration gate:** `make test` reports the full suite green (1753 passed, 5 skipped).

### Deliverable 3 — As-Built (Cleanup: docs + residual references)
- **README:** the `init prompts` bullet and the command-reference row now describe "bundled prompt Markdown files" instead of "prompt XMLs".
- **ARCHITECTURE.md:** the "Prompt Files Are Plaintext" bullet now names `*.md`/`MRP.md`; the session-root prompt rationale no longer mentions header injection; the removed header-injection step is replaced and the MRP append now documents `MRP.md` joined by a `---` separator; the overridable/non-overridable prompt bullets now name `*.md`/`MRP.md`.
- **prompt_manager.md (component doc):** the MRP section, the single-sourced-assembly section, the persist-then-reuse section, the `canonical_agent_name` sentence, the failure modes, the Ports list, the contract-dependency note, and both method contracts (`fetch_system_prompt`, `compose_system_prompt`) were rewritten to the as-built contract (no header injection, `MRP.md`, `---` separator). `Status` stays `Stable`.
- **init_service.md (component doc):** the MRP failure-mode name moved to `MRP.md`; the `check_drift` classifier moved to the Markdown prompt extension; and a new "Prompt Initialization Logic" section documents stem identity plus the stale-`.xml`-as-missing-`.md` drift behaviour. `Status` stays `Implemented`.
- **Enumerated specs:** `interactive-session-workflow.md` (mermaid node, directory tree, artifact description, prompt-assembly pipeline, teddy-start example, plan-generation references) and `teddy-directory-structure.md` (turn tree, `system_prompt` description) now use `.md`.
- **Unenumerated-but-stale docs swept:** `cli.md` (get-prompt description and behaviour step), `planning_service.md` (prompt-file references and the Fetch System Prompt step), `session_service.md` (Prompt Relocation + the removed-migration note), plus the example-only `context-payload-format.md` and `plan-format.md`.
- **Non-behavioural `src` docstrings/comments:** `drift_report.py` (basename example), `init.py` (two docstrings), and the `prompt_manager.py` MRP-seam comment moved to `.md`.
- **Consistency sweep:** `git grep -nF ".xml"` over `src/teddy_executor/resources` returns nothing; over `README.md`/`docs/architecture`/`docs/project/specs` returns only the intentional new `init_service.md` paragraph; over `src` returns only the seven intentional stem-identity/`.md`-priority descriptions (`init_service.py` 153/180/250, `prompt_manager.py:93`, `paths.py` 8/46, `prompts.py:11`).
- **Integration gate:** `make test` reports the full suite green (1753 passed, 5 skipped), confirming the docs-and-comments-only change set is behaviour-neutral.

### Appended Cleanup — As-Built (residual `src` docstrings/comments)
- **Origin:** Phase 6 Step 1 quality audit (Turn 54) found a bounded cluster of stale non-behavioural prompt-migration wording the narrow `.xml`/`Agent Name` sweep of Deliverable 3 missed.
- **`__main__.py`:** the `init prompts` docstring now says "bundled prompt Markdown files" (was "prompt XMLs"); the `get-prompt` docstring now describes "the agent-specific content and the shared Markdown MRP base prompt, separated by a Markdown horizontal rule" (was "the agent-name header, the agent-specific XML, and the shared MRP base prompt").
- **Outbound `prompt_manager.py`:** the `compose_system_prompt` contract docstring now reads "agent content + `---` separator + shared Markdown MRP base prompt".
- **Outbound `session_manager.py`:** the `set_session_agent` docstring now says "prompt file" (was "prompt XML").
- **Service `prompt_manager.py`:** `_resolve_agent_prompt_content` now resolves "the agent-specific prompt content" (was "prompt XML").
- **Service `session_service.py`:** the `create_session` comment, the `set_session_agent` docstring, and the recompose comment now use "agent content + `---` separator + MRP" and "prompt file" wording.
- **Non-behavioural:** all nine edits are docstrings and comments only; the integration gate confirms the suite stays green.
- **Consistency sweep:** `git grep -niF "xml" -- src/teddy_executor` returns only the intentional `.md`-priority/stem-identity descriptions (`init_service.py` 153/180/250, `prompt_manager.py:93`, `paths.py` 8/46, `prompts.py:11`) plus the unrelated `web_scraper_adapter.py:159` (`application/xhtml+xml` Accept header).

## Verification
- [x] Run `make test` and verify the full suite passes (green-to-green).
- [x] Run `git grep -nF ".xml" -- src/teddy_executor/resources` and verify it returns nothing.
- [x] Run `ls src/teddy_executor/resources/config/prompts/` and verify 6 `.md` files and no `.xml` files.
- [x] Run `teddy get-prompt pathfinder` and verify the output starts with `# Pathfinder`, contains a `---` separator line (with a blank line above and below) between the agent prompt and the Markdown MRP, and ends with the Markdown MRP content.
- [x] In a temp project with both `.teddy/prompts/pathfinder.xml` and `.teddy/prompts/pathfinder.md`, run `teddy get-prompt pathfinder` and verify the `.md` content is returned (`.md` wins).
- [x] In a temp project with `.teddy/prompts/pathfinder.xml` present, run `teddy start -y -m hello` and verify the preflight advises `teddy init prompts`.
- [x] In a temp project with `.teddy/prompts/pathfinder.xml` present, run `teddy init prompts` and verify `pathfinder.md` exists and `pathfinder.xml` is gone.
- [x] In a temp project with only `.teddy/prompts/pathfinder.xml`, run bare `teddy init` and verify no `pathfinder.md` is created (same-stem = present).
- [x] Run `teddy init templates` and verify templates are unaffected.

### Verification Evidence
- **Item 1:** `make test` reported the full suite green (1753 passed, 5 skipped) at the committed HEAD; the unskippable post-commit gate re-ran it green on the final commit (`124fc383`).
- **Items 2–3:** `git grep -nF ".xml" -- src/teddy_executor/resources` returns nothing; `ls src/teddy_executor/resources/config/prompts/` lists `architect.md`, `assistant.md`, `debugger.md`, `developer.md`, `pathfinder.md`, `prototyper.md` and no `.xml`.
- **Item 4:** `teddy get-prompt pathfinder --no-copy` emits `# Pathfinder` on line 1, a `---` separator on its own line (line 62), and the Markdown MRP block (exactly one `## Response Format`) at the end.
- **Item 5:** in a temp project containing both `pathfinder.xml` and `pathfinder.md`, `get-prompt` returned the `.md` content (`.md` marker present, `.xml` marker absent).
- **Item 6 (probe limitation):** a bare temp project cannot exercise this path via the CLI because the API-key/config preflight aborts (exit 1) before the drift advice is reached. The behaviour is instead proven by the passing acceptance test `tests/suites/acceptance/test_preflight_drift_notification.py::test_start_advises_init_prompts_when_a_prompt_has_drifted`, which seeds a stale `pathfinder.xml` and asserts the `teddy init prompts` advice fires. Marked PASS on that basis.
- **Item 7:** `teddy init prompts` wrote `pathfinder.md` and removed the stale `pathfinder.xml`, leaving exactly one same-stem file.
- **Item 8:** bare `teddy init` left the stale `pathfinder.xml` in place and created no `pathfinder.md` (same-stem counts as present).
- **Item 9:** `teddy init templates` wrote the ten bundled templates into `docs/templates/`, unaffected by the prompt migration.
