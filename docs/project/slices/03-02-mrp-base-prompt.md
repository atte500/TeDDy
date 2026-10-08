# Slice: MRP Base Prompt
- **Status:** Completed
- **Milestone:** [03-foundational-refactors](/docs/project/milestones/03-foundational-refactors.md)
- **Specs:** TBD (Milestone doc serves as spec)
- **Component Docs:** [PromptManager](/docs/architecture/core/services/prompt_manager.md)
- **Prototype:** [spikes/prototypes/mrp-base-prompt/](/spikes/prototypes/mrp-base-prompt/)
- **Scope Slug:** `mrp-base-prompt`

## Business Goal
Eliminate ~900 lines of duplicated protocol rules across all 6 agent prompts by extracting the shared Markdown Response Protocol (MRP) into a central `MRP.xml` base prompt. This makes protocol changes a single-point update and ensures all agents produce parseable output.

## Progress (Done vs To Do)

### Done (Design / Content Artifacts)
- [x] Created the MRP base prompt (now at `src/teddy_executor/resources/MRP.xml`) containing the shared `<general_rules>` (State Transition Protocol, State Dashboard format, Sequential Action Workflow, Path & Link Formatting, Information Gathering Workflow, VCP, Standardized Plan Types, Code Block Formatting, Validation Failure Recovery, Conflict Resolution Protocol, Programmatic Edits, Template-First Documentation) and the `<response_format>` block.
- [x] **Relocated MRP.xml** out of `src/teddy_executor/resources/config/prompts/` to `src/teddy_executor/resources/MRP.xml` (a 2026-10-08 decision) so it is never grouped with — or mistaken for — the user-overridable agent prompts. PromptManager MUST load it from the `teddy_executor.resources` package via `importlib.resources`.
- [x] Parameterized the plan metadata (`- **Agent:**`) so it resolves from the injected `Agent Name:` line at the top of the assembled prompt.
- [x] Removed all XML escape sequences (`&lt;` / `&gt;`) — prompts are plaintext, not parsed — and documented the convention in `docs/architecture/ARCHITECTURE.md`.
- [x] Removed the `- **Lines:**` option from the `READ` action definition.
- [x] Replaced the placeholder example with a lorem-ipsum Action-Plan example.
- [x] Updated the Milestone 3 spec for agent-name injection, MRP injection semantics (after the agent-specific XML, inside `<system>`), and legacy detection.
- [x] Remove the shared `<general_rules>` and `<response_format>` from all 6 agent XMLs; keep only agent-specific rules and renumber sequentially.

### To Do (Harness Code)
- [x] `PromptManager.fetch_system_prompt()`: inject `Agent Name: {agent}` before the agent-specific XML.
- [x] `PromptManager.fetch_system_prompt()`: load MRP.xml via `importlib.resources.files()` and append after the agent-specific content (inside `<system>`).
- [x] Legacy detection: skip MRP injection when the resolved prompt already contains `<response_format>`.
- [x] Fail-fast: raise `FileNotFoundError` when MRP.xml is missing.
- [x] Tests: agent-name injection, MRP append, legacy skip, missing-MRP failure, and agent-XML cleanup assertions.

## Scenarios

> As a user, I want my session's system prompt to include the MRP protocol rules so that all agents follow the same response format.

```gherkin
Given I have selected an agent (e.g., "developer") and am starting a session
When the system prompt is assembled for that agent
Then the assembled prompt contains the agent-specific XML content
And it also contains the shared MRP protocol rules (general rules 1-9, conflict resolution, programmatic edits, response format)
And the MRP rules appear AFTER the agent-specific content
```

> As a user, I want the agent name to be injected at the start of the system prompt so that the agent knows its identity during protocol processing.

```gherkin
Given I have selected an agent (e.g., "developer") and am starting a session
When the system prompt is assembled for that agent
Then the assembled prompt starts with "Agent Name: Developer" (where Developer is derived from the XML filename)

Given I select the "architect" agent
When the system prompt is assembled
Then the assembled prompt starts with "Agent Name: Architect"
```

> As a user, I want MRP.xml to NOT be copied to .teddy/prompts/ so that the protocol infrastructure cannot be accidentally modified.

```gherkin
Given I have an initialized project with .teddy/prompts/
When I search for MRP.xml in the .teddy/ directory
Then MRP.xml is NOT found in .teddy/prompts/ or anywhere in .teddy/
And MRP.xml is only present in the bundled package resources
```

> As an administrator, I want fetch_system_prompt() to raise a clear error if MRP.xml is missing so that protocol degradation is never silent.

```gherkin
Given MRP.xml is missing from src/teddy_executor/resources/
When fetch_system_prompt() is called for any agent
Then a FileNotFoundError is raised with a message indicating MRP.xml is missing
```

> As a user, I want agent-specific rules to remain in their respective XMLs so that agent-specific behavior is not lost during extraction.

```gherkin
Given I inspect any agent XML prompt
When I search for agent-specific rules
Then the Debugger XML still contains its Remote Probing Protocol rule
And the Developer XML still contains its Contract Enforcement rule
And the Architect XML still contains its Programmatic Edits rule (if renamed/numbered differently from the shared set)
And the Pathfinder XML still contains its Handoff Targets and blueprint definitions for its workflow
```

## Edge Cases
- **MRP.xml resource missing**: If MRP.xml is absent from `src/teddy_executor/resources/`, `fetch_system_prompt()` MUST raise a clear `FileNotFoundError`. This is a fatal protocol error — agents will produce non-parseable output without the MRP rules.
- **Agent-specific rules preserved**: Only the shared rules (1-9, Conflict Resolution, Programmatic Edits) and `<response_format>` are extracted to MRP.xml. Agent-specific rules (e.g., Debugger's RPP rule 11, Developer's Contract Enforcement rule 10) remain in their respective XMLs.
- **Empty MRP.xml**: If MRP.xml exists but is empty, `fetch_system_prompt()` should still succeed (append empty string) rather than raising an error. The file presence indicates intent, but zero-length content is a degenerate case.

## Key Unknowns
- [x] [Technical] MRP.xml location: Approved by user — RELOCATED OUT of `src/teddy_executor/resources/config/prompts/` so it is NOT bundled/grouped with the user-overridable agent prompts. New home: `src/teddy_executor/resources/MRP.xml`, loaded via `importlib.resources.files("teddy_executor.resources") / "MRP.xml"`.
- [x] [Technical] `importlib.resources` API for loading MRP.xml: RESOLVED & EMPIRICALLY VERIFIED (spike at [spikes/prototypes/mrp-base-prompt/](/spikes/prototypes/mrp-base-prompt/), evidence in FINDINGS.md). Use `importlib.resources.files("teddy_executor.resources") / "MRP.xml"`, then `.read_text(encoding="utf-8")`. In this source checkout `files()` returns a `pathlib.PosixPath` whose `is_file()` is True; production code MUST use only the `Traversable` contract (`is_file`, `read_text`) so it also works under zip/wheel installs. A missing MRP.xml raises `FileNotFoundError` both naturally (via `read_text` on a non-existent name) and via the explicit `is_file()`-guarded fail-fast pattern production should adopt. The existing `prompts.py` still does NOT load from bundled resources; PromptManager loads MRP.xml directly.

## Implementation Plan

### Overview
This slice has one technical unknown that should be de-risked by the Prototyper before the Developer begins. The core work is: (1) create MRP.xml with extracted shared content, (2) modify PromptManager to load and append it, and (3) remove the now-redundant content from agent XMLs.

### Detailed Tech Strategy

#### MRP.xml Loading
PromptManager's `fetch_system_prompt()` currently resolves agent XMLs via the filesystem hierarchy. For MRP.xml — which deliberately lives OUTSIDE `config/prompts/` so it is not grouped with agent prompts — it MUST load directly from the `teddy_executor.resources` package using `importlib.resources`:
```python
import importlib.resources as resources

# In fetch_system_prompt, after resolving agent XML content:
mrp_xml_path = resources.files("teddy_executor.resources") / "MRP.xml"
mrp_content = mrp_xml_path.read_text(encoding="utf-8")
```
This bypasses `.teddy/prompts/` entirely — MRP.xml is NEVER user-editable.

#### Agent XML Modifications
Each of the 6 XMLs needs identical changes:
1. Remove the entire `<general_rules>` block (rules 1-9 plus 10 Conflict Resolution and 11 Programmatic Edits).
2. Remove the entire `<response_format>` block.
3. Preserve any agent-specific rules that are NOT in the shared set (e.g., Debugger's RPP, Developer's Contract Enforcement).

#### Content to Extract to MRP.xml
The MRP.xml should contain:
- The complete `<response_format>` block (shared across all agents)
- Shared `<general_rules>` rules 1-9 (State Transition Protocol, State Dashboard, Sequential Action Workflow, Path & Link Formatting, Information Gathering Workflow, VCP, Standardized Plan Types, Code Block Formatting, Validation Failure Recovery)
- Rule 10 (Conflict Resolution Protocol) — shared
- Rule 11 (Programmatic Edits) — shared

#### Agent Name Injection
`fetch_system_prompt()` must inject the agent name at the very start of the assembled system prompt, before the agent-specific XML and MRP content. The agent name is derived from the XML filename (e.g., `architect.xml` → `Architect`). The format is a single line, `Agent Name: {AgentName}` (capitalized; no leading `#`), followed by a blank line and the agent-specific XML content. The `agent_name` parameter already exists as a string input; it is capitalized for display.

### Deliverables
- [x] **Contract** - MRP base prompt at `src/teddy_executor/resources/MRP.xml` with extracted shared content (shipped).
- [x] **Cleanup** - Shared `<general_rules>` and `<response_format>` blocks removed from all 6 agent XMLs. This was completed as part of the content work (the "Done" section above marks it `[x]`) and was empirically re-verified on 2026-10-08: `git grep` finds zero occurrences of either marker under `src/teddy_executor/resources/config/prompts/`. No code work remains.
- [x] **Logic** - Modify `PromptManager` to (1) inject the `Agent Name: {CapitalizedAgentName}` header before the agent-specific content, (2) load `MRP.xml` through an injectable resource seam (`mrp_resource_root`, defaulting to `importlib.resources.files("teddy_executor.resources")`, following the `InitService` pattern) using only the `Traversable` contract (`is_file` + `read_text`), (3) append the MRP content after the agent-specific content, (4) skip ONLY the MRP append when the resolved prompt already contains `<response_format>` (legacy user override), and (5) raise `FileNotFoundError` when `MRP.xml` is missing. Bundled with unit tests: happy path, agent-name capitalization, legacy skip, missing-MRP failure, empty-MRP, and missing-agent-XML. The former `Harness` deliverable is folded here — its content is unit tests, which bundle with `Logic` — including the injectable seam's test fixture.
- [x] **Wiring** - Acceptance behavioral gate: drive a session against the harness fake LLM and assert the captured system prompt contains the `Agent Name:` header, the agent-specific content, and the MRP protocol rules end-to-end.

### Key Unknown Resolution Strategy
Before the Developer starts, the Prototyper should verify:
1. `importlib.resources.files("teddy_executor.resources")` correctly resolves to the resources package root (where MRP.xml now lives).
2. `read_text(encoding="utf-8")` works on the Traversable returned by `files()`.
3. The FileNotFoundError scenario reproduces correctly when MRP.xml is absent.

The Prototyper spike lives at `spikes/prototypes/mrp-base-prompt/`.

## Verification
1. [x] Run `pytest tests/suites/unit/core/services/test_prompt_manager.py -v` — all existing tests pass, new MRP injection tests pass.
2. [x] Run full test suite: `pytest` — all tests pass (green-to-green).
3. [x] Manual: `cat src/teddy_executor/resources/config/prompts/architect.xml | grep -c "<general_rules>"` — returns 0 (shared rules extracted).
4. [x] Manual: `cat src/teddy_executor/resources/config/prompts/architect.xml | grep -c "<response_format>"` — returns 0 (response format extracted to MRP.xml).
5. [x] Manual: `cat .teddy/prompts/architect.xml` — confirms MRP.xml NOT present in .teddy/prompts/.
6. [x] Manual: `cat src/teddy_executor/resources/MRP.xml | grep -c "State Transition Protocol"` — returns at least 1 (MRP rules present).
7. [x] Manual: `cat src/teddy_executor/resources/config/prompts/debugger.xml | grep -c "Remote Probing Protocol"` — returns at least 1 (agent-specific rule preserved).
8. [x] Manual: Run a session with the developer agent and capture the system prompt. Verify it starts with "Agent Name: Developer" followed by the XML content.
9. [x] Unit test: Verify that `fetch_system_prompt("architect", turn_path)` returns a string starting with "Agent Name: Architect".

## Implementation Notes

### Logic deliverable — MRP injection & agent-name header (implemented 2026-10-08)

**Seam decision.** MRP loading is made testable via an *additive, optional* constructor parameter
`mrp_resource_root: Any = None` on `PromptManager`. When `None`, the bundled package resource is
resolved lazily inside `_load_mrp_base_prompt()` via
`importlib.resources.files("teddy_executor.resources")`. Tests inject a real `pathlib.Path` root
(a `tmp_path` directory) instead of patching `importlib.resources`, satisfying the anti-mock-poisoning
rule with zero global patching. This is non-breaking: `PromptManager` has one production instantiation
(`container.py`) and four keyword-arg test constructions — none affected by the new defaulted param.
This mirrors the existing `InitService(config_dir=...)` seam pattern.

**Fail-fast loader.** `_load_mrp_base_prompt()` uses only the `Traversable` contract
(`is_file()` + `read_text(encoding="utf-8")`) so it works both in a source checkout and under a
zip/wheel install. A missing `MRP.xml` raises a domain-specific `FileNotFoundError` (the slice's
fatal-protocol-error requirement); an empty `MRP.xml` is deliberately allowed (append-empty). The
extractor `_resolve_agent_prompt_content()` was pulled out of `fetch_system_prompt()` to keep the
method focused (SRP).

**Assembly.** `fetch_system_prompt()` returns `Agent Name: {agent.capitalize()}\n\n{agent XML}` and
appends `\n\n{MRP}` only when the resolved content does NOT contain `<response_format>` (legacy
user-override detection). The `header + content` prefix is assembled once and reused across both
return branches.

**Missing agent XML.** Preserved the historical `return ""` early-return (no header, no MRP), which
also avoids a spurious MRP load and keeps the graceful-degradation contract intact.

**Deliberate divergence from the Milestone doc.** The Milestone 3 text says the legacy branch should
"return the resolved content as-is"; the slice + user instruction mandate injecting the agent-name
header while skipping only the MRP append. Followed the slice/user mandate; documented here.

**Tests bundled (unit layer).** Happy-path assembly, agent-name capitalization, legacy-skip,
missing-MRP failure, empty-MRP, and missing-agent-XML — plus two repaired pre-existing tests whose
assertions encoded the pre-injection return value
(`test_prompt_manager.py::test_fetch_system_prompt_resolves_from_teddy_prompts`,
`test_bug_03_prompt_resolution.py::test_fetch_system_prompt_ignores_case`). A shared
`mrp_prompt_manager` fixture was extracted to remove construction duplication within the file.

**As-Built update (completed with the Wiring deliverable).** `docs/architecture/core/services/prompt_manager.md`
was corrected to reflect the as-built reality: the MRP path (`resources/MRP.xml`), the agent-name header
format (`Agent Name: {Name}`, no leading `#`), the injectable `mrp_resource_root` seam, and the `Stable` status.

**Delivery recovery — pre-commit bypass (Logic VCP).** The first Logic VCP attempt aborted at the
staged-file Ruff hook on a pre-existing `TID251` mock-ban (`unittest.mock.MagicMock`/`patch`) at
`tests/suites/unit/core/services/test_bug_03_prompt_resolution.py:4`, which serves the out-of-scope
`TestLifecyclePrintsInitialRequest` class. `git show HEAD:…` confirmed the imports predate this
slice. Per the Delivery recovery protocol (refactor-or-log-and-bypass), the occurrence was folded
into the consolidated PROJECT.md debt entry and the VCP is committed with `--no-verify` for the
pre-commit stage only; the unskippable post-commit full-suite gate still runs.

### Wiring deliverable — acceptance behavioral gate (implemented 2026-10-08)

**Boundary & seam.** The gate is a subcutaneous end-to-end test in the Acceptance layer
(`tests/suites/acceptance/test_mrp_prompt_assembly.py`). It drives a real session through the CLI
(`start -y -m "instructions"`) against a real-filesystem-anchored `TestEnvironment`
(`.setup().with_real_shell()`, which deep-swaps the container and registers a real
`LocalFileSystemAdapter(root_dir=tmp_path)`), then reads the system prompt the injected `ILlmClient`
mock received via `llm.get_completion.call_args[1]["messages"][0]["content"]`. The real, bundle-backed
`PromptManager` is exercised (it is NOT in `TestEnvironment._register_default_mocks()`), so MRP.xml is
loaded from the bundled `teddy_executor.resources` package with no seam injection needed in this layer.
Imports are limited to the `ILlmClient` outbound port + harness, satisfying the Acceptance boundary.

**Assertions.** The captured system prompt (1) starts with `Agent Name: Pathfinder`, (2) contains the
seeded agent-specific content `<prompt>Pathfinder</prompt>`, and (3) contains the shared MRP rules
(`<response_format>` + `State Transition Protocol`), with (2) ordered before (3). This is the slice's
final behavioral gate and passed on first execution — the `Logic` deliverable (commit `a34494ed`) had
already wired the real behavior, so the tracer bullet was pre-established. No production code changed.

**Refactor.** Removed three unnecessary `# type: ignore` comments: `TestEnvironment.get_service`
returns `Any` and the harness mock is untyped, so neither the abstract-class argument nor the
`get_completion` attribute access required suppression (the canonical acceptance tests make the
identical calls ignore-free).
