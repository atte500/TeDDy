# Slice: Prompt Composition & Path Normalization Consolidation
- **Status:** Completed
- **Milestone:** N/A (ad-hoc)
- **Specs:** [docs/project/specs/interactive-session-workflow.md](/docs/project/specs/interactive-session-workflow.md)
- **Prototype:** N/A
- **Component Docs:** [PromptManager](/docs/architecture/core/services/prompt_manager.md), [SessionService](/docs/architecture/core/services/session_service.md), [CLI Adapter](/docs/architecture/adapters/inbound/cli.md)
- **Scope Slug:** `prompt-composition`

## Business Goal

Restore correctness of the CHOP workflow surface: `teddy get-prompt <agent>` must emit the full composed system prompt (agent-name header + agent XML + shared MRP base prompt) so a pasted prompt makes the model emit executable Markdown plans, and `-c` / `--context` must accept Markdown-link paths (`[label](target)`) and seed the target. Alongside these two defect repairs, single-source the path-normalization logic currently duplicated across the session, pruning, validation, parser, replanner, and filesystem layers so the link-aware capability and any future normalization rule propagate everywhere at once.

## Scenarios

> As a CHOP user, I want `get-prompt` to emit the full composed prompt so that pasting it into a web chat's system prompt actually produces executable plans.

```gherkin
Given a project with .teddy/prompts/pathfinder.xml containing "<prompt>Pathfinder</prompt>"
When I run `teddy get-prompt pathfinder --no-copy`
Then the output starts with "Agent Name: Pathfinder"
And the output contains the raw agent XML "<prompt>Pathfinder</prompt>"
And the output contains the shared MRP base prompt (the "<response_format>" block)
And the MRP block appears AFTER the agent-specific content
```

> As a user, I want `-c` to accept a Markdown link so I can paste a link straight from a document.

```gherkin
Given a project initialized with .teddy/init.context
When I start a session with `-c "[docs/readme.md](docs/readme.md)"`
Then session.context contains "docs/readme.md"
And session.context does NOT contain the literal "[docs/readme.md](docs/readme.md)"
```

> As a maintainer, I want one normalization function so path handling cannot drift across modules.

```gherkin
Given the shared pure path-normalization helper
When any consumer (session seeding, pruning, validation, parser, replanner, filesystem) normalizes a resource path
Then it delegates to the shared helper
And the five pre-existing normalization contracts are preserved
```

## Edge Cases

- **Legacy override**: If a resolved agent prompt already contains `<response_format>`, keep the `Agent Name:` header but do NOT inject the MRP block (preserve existing behavior).
- **Prompt not found**: `get-prompt <unknown>` must keep the current error message and exit code 1 (listing available prompts).
- **Agent casing**: The header must use `canonical_agent_name` (e.g. `pathfinder` -> `Pathfinder`).
- **Existing normalization preserved**: `-c` leading-slash strip, `./` strip, backslash normalization, `.hidden` leading-dot preservation, and empty-entry skipping must all still hold.
- **Link with backslashes**: `[label](docs\readme.md)` must normalize the extracted target to `docs/readme.md`.
- **Missing init.context**: `_prepare_session_context` keeps its `FileNotFoundError` fail-fast.
- **Call-site semantics**: If any duplicated call site normalizes WITHOUT link-stripping or `./`-stripping, migrate it only when the shared helper is a strict superset for its inputs; otherwise keep its local rule documented (no silent behavior change).

## Key Unknowns

- [x] [Formal] Slice numbering/milestone: Resolved — ad-hoc `00-35` (the driving defects are ad-hoc; the user directed the Milestone-6 normalization debt to be absorbed into this slice rather than scheduled separately).
- [x] [Technical] Does adding an abstract method to `IPromptManager` break consumers? Resolved — `PromptManager` is the sole PRODUCTION implementer, but the TEST suite constructs `PromptManager` directly at eight sites (`test_prompt_manager.py`, `test_bug_03_prompt_resolution.py`, `test_bug_19_model_prefix_preservation.py`, `test_session_service_pruning.py`), so the port method and its implementation MUST land atomically (merged `Contract` deliverable).
- [x] [Technical] Does `_extract_resource_path` preserve existing `-c` normalization? Resolved — preservation probe passed all five cases plus the link case.
- [x] [Technical] Do all six duplicated call sites share identical normalization semantics with the extracted helper? Resolved — NO. Only `session_pruning_service.py:74,97` and `validation_rules/helpers.py:167,173` share the exact full pipeline. The parser helpers (`normalize_path` percent-decodes and preserves URLs; `normalize_link_target` does OS-aware absolute-path detection) and `local_file_system_adapter._resolve_path` (drive-letter handling) have genuinely divergent semantics; `session_pruning_service.py:145`, `session_replanner.py:97`, `filesystem_helpers.py:63`, and `local_file_system_adapter.py:137` are partial. Migration is scoped to the strict-superset sites; divergent/partial sites keep and document their local rule.

## Implementation Plan

**Defect A (prompt composition).** Extract an `_assemble_composed_prompt(agent_name, content)` helper inside `PromptManager` from the lazy-compose branch of `fetch_system_prompt`, keeping the `<response_format>` legacy short-circuit. Reuse it inside `fetch_system_prompt` and expose a turn-path-free `compose_system_prompt(agent_name) -> Optional[str]` on `IPromptManager` (abstract) and `PromptManager` (resolve content via `get_prompt_content`, return `None` when unresolved). Rewire the `get-prompt` command to resolve `IPromptManager` from the base container (no `_ensure_project_initialized` required — its dependencies are base-registered) and echo `compose_system_prompt(prompt_name)`; keep the not-found branch unchanged.

**Defect B (context links).** In `SessionService._prepare_session_context`, replace the inline per-entry normalization with a call to the existing `_extract_resource_path`. This single-sources normalization and gains `[label](target)` extraction with no regression (proven by the preservation probe).

**Consolidation (paid debt).** Extract a module-level pure function `core/utils/paths.py::normalize_resource_path` equivalent to `_extract_resource_path`, delegate `SessionService._extract_resource_path` to it, and migrate only the call sites for which it is a strict superset (`session_pruning_service.py:74,97`, `validation_rules/helpers.py:167,173`). The parser percent-decoding/URL helpers, the `_resolve_path` drive-letter logic, and the partial-normalization sites are intentionally NOT migrated (each local rule kept and documented) to avoid silent behavior changes.

Order: A and B are independent and each test-first; consolidation follows, migrated one call site at a time with the full suite green between migrations.

## Deliverables

- [x] **Contract** - Add `compose_system_prompt(self, agent_name: str) -> Optional[str]` to `IPromptManager` AND implement it in `PromptManager` atomically: extract `_assemble_composed_prompt(agent_name, content)` from `fetch_system_prompt`'s lazy-compose branch (preserving the `<response_format>` legacy short-circuit), reuse it inside `fetch_system_prompt`, and implement `compose_system_prompt` (resolve content via `get_prompt_content`, return `None` when unresolved). Merged with the former `Logic` deliverable: adding the abstract method without its implementation makes `PromptManager` un-instantiable and breaks the eight test sites that construct it directly.
- [x] **Wiring** - Rewire the `get-prompt` command in `__main__.py` to resolve `IPromptManager` from the base container and echo `compose_system_prompt(prompt_name)`; keep the not-found branch unchanged. Test-first: delivered with its happy-path acceptance test asserting the composed output (agent-name header + agent XML + MRP base prompt, in order); the not-found exit-1 branch is already covered by the pre-existing `test_get_prompt_fails_for_non_existent_prompt`.
- [x] **Logic** - Route `SessionService._prepare_session_context` entries through `_extract_resource_path`, delivered with its unit test covering `-c` Markdown-link parsing plus the five preserved normalization cases.
- [x] **Refactor** - Extract a shared pure helper `core/utils/paths.py::normalize_resource_path(resource_str)` (link-aware extraction + the full normalization pipeline: backslash → slash, strip the exact `./` prefix, strip leading `/`) and delegate `SessionService._extract_resource_path` to it, delivered with its unit test covering all normalization cases (incl. link extraction).
- [x] **Refactor** - Migrate the strict-superset duplicated call sites to `normalize_resource_path`: `session_pruning_service.py:74,97` and `validation_rules/helpers.py:167,173`. Do NOT migrate the divergent sites (`parser_infrastructure.py:114` percent-decoding + URL preservation, `:136` OS-aware absolute-path detection, `local_file_system_adapter.py:56,62` drive-letter resolution) nor the partial sites (`session_pruning_service.py:145`, `session_replanner.py:97`, `filesystem_helpers.py:63`, `local_file_system_adapter.py:137`) unless the helper is confirmed a strict superset for their inputs; otherwise keep and document each local rule (no silent behavior change).

## Implementation Notes

_Sandbox-proven: both fixes were validated via the Shadow File methodology (MREs + shadow replicas) before any production edit; the full verification record lives in [Case File 05](/docs/project/debugging/05-get-prompt-composition-and-context-links.md) (Investigation History entries 7-10)._

### Contract deliverable — `compose_system_prompt` (prompt-composition)

- **What shipped.** Added the abstract `compose_system_prompt(self, _agent_name: str) -> Optional[str]` to `IPromptManager`, and implemented it on `PromptManager`. Extracted `_assemble_composed_prompt(agent_name, content)` from `fetch_system_prompt`'s lazy-compose branch; `fetch_system_prompt` now delegates to it (byte-identical logic, so its empty-content `""` contract is preserved at the caller), and `compose_system_prompt` resolves content via the existing public `get_prompt_content` seam, returning `None` when unresolved (the CLI's not-found signal).
- **Why it landed atomically.** `IPromptManager` is an ABC and the test suite constructs `PromptManager` directly at eight sites; adding the abstract method without its implementation would have rendered the concrete class un-instantiable and reddened those sites. The port method and its implementation were therefore merged into a single deliverable.
- **Red evidence.** Five `compose_system_prompt` items failed with `AttributeError: '_StubContentPromptManager' object has no attribute 'compose_system_prompt'` before the change — a genuine absence, not a fixture error.
- **Green evidence.** `tests/suites/unit/core/services/test_prompt_manager.py` → 19 passed (5 new + 14 pre-existing); full suite (`make test`) → 1730 passed, 5 skipped.
- **Test design.** The new method resolves content through `get_prompt_content` → `prompts.find_prompt_content` → the REAL `Path.cwd()`, bypassing `IFileSystemManager`. The tests inject content via a hand-written `_StubContentPromptManager` subclass overriding only that public seam (no global patching, no bare mock); the MRP half uses a real `tmp_path` resource root injected through `mrp_resource_root=`.

### Wiring deliverable — `get-prompt` composed output (prompt-composition)

- **What shipped.** Rewired `get_prompt` in `src/teddy_executor/__main__.py` to resolve `IPromptManager` from the base container (`get_container().resolve(IPromptManager)`) and echo `prompt_manager.compose_system_prompt(prompt_name)`, replacing the former direct call to `prompts.find_prompt_content`. The not-found branch (`list_prompt_names()` listing + `typer.Exit(code=1)`) was left byte-for-byte unchanged, so its pre-existing coverage (`test_get_prompt_fails_for_non_existent_prompt`) still applies verbatim.
- **Why no `_ensure_project_initialized`.** `IPromptManager` is bound transiently on the BASE container (`container.py:218-222`, inside `_register_orchestration_services`, which `create_container` always runs), and its only dependencies (`IFileSystemManager`, `IUserInteractor`) are registered even earlier by `register_infrastructure`. Resolving the port therefore needs no project anchoring, mirroring the existing boundary precedent in `session_cli_handlers.py:722`.
- **Red evidence.** The new acceptance test failed with `AssertionError: assert False ... '<prompt>Pathfinder</prompt>\n'.startswith('Agent Name: Pathfinder')` — the raw fragment, no header/MRP — a genuine defect, and independent proof that the harness CWD wiring (`CliTestAdapter.run_cli_command` → `monkeypatch.chdir`) resolves the seeded `.teddy/prompts/pathfinder.xml`.
- **Green evidence.** `tests/suites/acceptance/test_cli_ux_improvements.py` → 5 passed (new composed-output test + the two pre-existing get-prompt tests + two CLI tests); full suite (`make test`) → 1731 passed, 5 skipped.
- **Test design.** The acceptance test drives the outermost CLI boundary via the shared `CliTestAdapter`/`TestEnvironment` (no internal core models/services imported), seeding a real `.teddy/prompts/pathfinder.xml` and asserting the header + agent XML + MRP block ordering.

### Logic deliverable — `-c` Markdown-link extraction (prompt-composition)

- **What shipped.** In `SessionService._prepare_session_context`, replaced the inline per-entry normalization loop (`path.strip().replace("\\", "/")`, `[2:]` on a `./` prefix, `lstrip("/")`) with a delegation to the existing canonical link-aware helper `self._extract_resource_path(entry)`, preserving BOTH guards: the `if entry:` empty-entry skip and the `if normalized and normalized not in clean_lines` dedup. The `FileNotFoundError` fail-fast on a missing `.teddy/init.context` is untouched (it precedes the loop).
- **Why it is correct.** `_extract_resource_path`'s non-link branch is byte-identical to the prior inline rule (`strip` + backslash→slash + exact `./` removal + `lstrip("/")`), and it additionally matches `[label](target)` and extracts the target — a proven strict superset (Case File 05, Investigation History entries 7 & 10). For non-link inputs the new path is behaviour-identical to the old.
- **Red evidence.** The new `test_markdown_link_entry_extracts_target` (parametrized forward- and back-slash targets) failed with `AssertionError: assert 'docs/readme.md' in ['some/path.md', '[docs/readme.md](docs/readme.md)']` before the change — the raw link survived verbatim.
- **Green evidence.** `tests/suites/unit/core/services/test_cli_arg_normalization_regression.py` → 12 passed (2 new link params + 6 pre-existing normalization + 4 case-insensitivity); full suite (`make test`) → 1733 passed, 5 skipped.
- **Test design.** The new case extends the existing `TestContextPathNormalization` class, reusing its `service` fixture and asserting on whole LINES (`"docs/readme.md" in lines`) rather than substring membership, because the target is a substring of the raw link and a plain `in result` check would yield a false Green.

### Refactor deliverable — `normalize_resource_path` extraction (prompt-composition)

- **What shipped.** Created `src/teddy_executor/core/utils/paths.py` exposing the module-level pure function `normalize_resource_path(resource_str)` — a verbatim lift of the former `SessionService._extract_resource_path` body (the compiled `_LINK_PATTERN` link branch plus the `strip`/backslash/`./`/`lstrip("/")` raw branch). `SessionService._extract_resource_path` is now a one-line delegate, and the new import sits beside the sibling `core.utils.string` import.
- **Why it is correct.** The extraction is byte-for-behaviour identical: the link branch does NOT `.strip()` the extracted group (only the raw branch strips), and the exact-`./`-prefix rule preserves leading dots such as `.hidden`. `_LINK_PATTERN` is hoisted to module scope so the regex is compiled once. This single-sources the pipeline so the second `Refactor` deliverable (strict-superset call-site migration) can delegate every migrated site to one canonical rule.
- **Red evidence.** The new `tests/suites/unit/core/utils/test_paths.py` failed at COLLECTION with `ModuleNotFoundError: No module named 'teddy_executor.core.utils.paths'` — a genuine absence, not a fixture error.
- **Green evidence.** `tests/suites/unit/core/utils/test_paths.py tests/suites/unit/core/services/test_session_service_extraction.py` → 10 passed (9 parametrized helper cases + the pre-existing delegating-method case); full suite (`make test`) → 1742 passed, 5 skipped.
- **Test design.** A parametrized unit test covers the full pipeline (link forward/back-slash and mixed-slash targets, raw backslash normalization, leading-slash strip, `./` strip, `.hidden` preservation, whitespace trim, empty input). The pre-existing `test_extract_resource_path_normalizes_slashes` continues to guard the delegating instance method, proving the delegation is behaviour-preserving.

### Refactor deliverable — strict-superset call-site migration (prompt-composition)

- **What shipped.** Migrated the four call sites that shared the EXACT full normalization pipeline to delegate to `core/utils/paths.py::normalize_resource_path`: `session_pruning_service.py::_process_context_item` (~line 74) and `::_extract_turn_id` (~line 97), plus both `normalized_target` and `normalized_context` in `validation_rules/helpers.py::is_path_in_context` (~lines 167, 173). Each host file gained the shared-helper import.
- **Why it is correct.** The helper's non-link branch is a byte-identical strict superset of each inline pipeline for raw paths (the only added operation being a harmless `.strip()`), so every pre-existing raw-path assertion remains Green; for link-shaped inputs the helper additionally extracts the `[label](target)` target. Both migrated behaviours therefore gain link-awareness without any raw-path behaviour change.
- **Deliberately NOT migrated.** The divergent sites (`parser_infrastructure.py:114,136` — percent-decoding + URL preservation / OS-aware absolute-path detection; `local_file_system_adapter.py:56,62` — drive-letter resolution) and the partial-normalization sites (`session_pruning_service.py:145`, `session_replanner.py:97`, `filesystem_helpers.py:63`, `local_file_system_adapter.py:137`) each keep and document their local rule — no silent behaviour change.
- **Red evidence.** Three link-awareness tests failed as expected: `test_is_path_in_context_extracts_markdown_link_target` (both parametrizations) with `AssertionError: assert False is True`, and `test_extract_turn_id_extracts_target_from_markdown_link` with `AssertionError: assert None == '01'`; the 8 pre-existing raw-path tests still passed.
- **Green evidence.** `tests/suites/unit/core/services/test_validation_helpers.py tests/suites/unit/core/services/test_session_pruning_service_refinement.py` → 11 passed (3 newly Green + 8 pre-existing); full suite (`make test`) → 1745 passed, 5 skipped.
- **Test design.** The gained capability (link extraction) is asserted at the two host modules via a parametrized `is_path_in_context` case (forward- and back-slash targets) and a `_extract_turn_id` case (`[01/report.md](01/report.md)` → `"01"`), keeping every pre-existing raw-path assertion as the behaviour-preservation gate.

## Verification

1. [x] `teddy get-prompt pathfinder` prints `Agent Name: Pathfinder`, the agent XML, and the MRP `<response_format>` block, in that order.
2. [x] `teddy get-prompt <unknown>` prints the not-found error and exits non-zero.
3. [x] `teddy start -m "hi" -c "[docs/readme.md](docs/readme.md)"` seeds `docs/readme.md` (not the literal link) into `session.context`.
4. [x] The five pre-existing `-c` normalization cases still pass (leading slash, `./`, backslashes, `.hidden`, empty entry).
5. [x] `make test` is green after each migration step and at slice completion.
