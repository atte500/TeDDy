# Slice: Prompt Composition & Path Normalization Consolidation
- **Status:** In Progress
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
- [ ] **Wiring** - Rewire the `get-prompt` command in `__main__.py` to resolve `IPromptManager` from the base container and echo `compose_system_prompt(prompt_name)`; keep the not-found branch unchanged.
- [ ] **Harness** - Acceptance test asserting composed `get-prompt` output (header + agent XML + MRP, in order) and the not-found exit-1 branch.
- [ ] **Logic** - Route `SessionService._prepare_session_context` entries through `_extract_resource_path`.
- [ ] **Harness** - Unit test for `-c` link parsing plus the five preserved normalization cases.
- [ ] **Refactor** - Extract a shared pure helper `core/utils/paths.py::normalize_resource_path(resource_str)` (link-aware extraction + the full normalization pipeline: backslash → slash, strip the exact `./` prefix, strip leading `/`) and delegate `SessionService._extract_resource_path` to it.
- [ ] **Refactor** - Migrate the strict-superset duplicated call sites to `normalize_resource_path`: `session_pruning_service.py:74,97` and `validation_rules/helpers.py:167,173`. Do NOT migrate the divergent sites (`parser_infrastructure.py:114` percent-decoding + URL preservation, `:136` OS-aware absolute-path detection, `local_file_system_adapter.py:56,62` drive-letter resolution) nor the partial sites (`session_pruning_service.py:145`, `session_replanner.py:97`, `filesystem_helpers.py:63`, `local_file_system_adapter.py:137`) unless the helper is confirmed a strict superset for their inputs; otherwise keep and document each local rule (no silent behavior change).
- [ ] **Harness** - Unit test for `normalize_resource_path` covering all normalization cases (incl. link extraction).

## Implementation Notes

_Sandbox-proven: both fixes were validated via the Shadow File methodology (MREs + shadow replicas) before any production edit; the full verification record lives in [Case File 05](/docs/project/debugging/05-get-prompt-composition-and-context-links.md) (Investigation History entries 7-10)._

### Contract deliverable — `compose_system_prompt` (prompt-composition)

- **What shipped.** Added the abstract `compose_system_prompt(self, _agent_name: str) -> Optional[str]` to `IPromptManager`, and implemented it on `PromptManager`. Extracted `_assemble_composed_prompt(agent_name, content)` from `fetch_system_prompt`'s lazy-compose branch; `fetch_system_prompt` now delegates to it (byte-identical logic, so its empty-content `""` contract is preserved at the caller), and `compose_system_prompt` resolves content via the existing public `get_prompt_content` seam, returning `None` when unresolved (the CLI's not-found signal).
- **Why it landed atomically.** `IPromptManager` is an ABC and the test suite constructs `PromptManager` directly at eight sites; adding the abstract method without its implementation would have rendered the concrete class un-instantiable and reddened those sites. The port method and its implementation were therefore merged into a single deliverable.
- **Red evidence.** Five `compose_system_prompt` items failed with `AttributeError: '_StubContentPromptManager' object has no attribute 'compose_system_prompt'` before the change — a genuine absence, not a fixture error.
- **Green evidence.** `tests/suites/unit/core/services/test_prompt_manager.py` → 19 passed (5 new + 14 pre-existing); full suite (`make test`) → 1730 passed, 5 skipped.
- **Test design.** The new method resolves content through `get_prompt_content` → `prompts.find_prompt_content` → the REAL `Path.cwd()`, bypassing `IFileSystemManager`. The tests inject content via a hand-written `_StubContentPromptManager` subclass overriding only that public seam (no global patching, no bare mock); the MRP half uses a real `tmp_path` resource root injected through `mrp_resource_root=`.

## Verification

1. `teddy get-prompt pathfinder` prints `Agent Name: Pathfinder`, the agent XML, and the MRP `<response_format>` block, in that order.
2. `teddy get-prompt <unknown>` prints the not-found error and exits non-zero.
3. `teddy start -m "hi" -c "[docs/readme.md](docs/readme.md)"` seeds `docs/readme.md` (not the literal link) into `session.context`.
4. The five pre-existing `-c` normalization cases still pass (leading slash, `./`, backslashes, `.hidden`, empty entry).
5. `make test` is green after each migration step and at slice completion.
