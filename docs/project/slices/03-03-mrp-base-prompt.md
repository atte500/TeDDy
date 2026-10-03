# Slice: MRP Base Prompt
- **Status:** Planned
- **Milestone:** [03-foundational-refactors](/docs/project/milestones/03-foundational-refactors.md)
- **Specs:** TBD (Milestone doc serves as spec)
- **Component Docs:** [PromptManager](/docs/architecture/core/services/prompt_manager.md)
- **Scope Slug:** `mrp-base-prompt`

## Business Goal
Eliminate ~900 lines of duplicated protocol rules across all 6 agent prompts by extracting the shared Markdown Response Protocol (MRP) into a central `MRP.xml` base prompt. This makes protocol changes a single-point update and ensures all agents produce parseable output.

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
Given MRP.xml is missing from src/teddy_executor/resources/config/prompts/
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
- **MRP.xml resource missing**: If MRP.xml is absent from `src/teddy_executor/resources/config/prompts/`, `fetch_system_prompt()` MUST raise a clear `FileNotFoundError`. This is a fatal protocol error — agents will produce non-parseable output without the MRP rules.
- **Agent-specific rules preserved**: Only the shared rules (1-9, Conflict Resolution, Programmatic Edits) and `<response_format>` are extracted to MRP.xml. Agent-specific rules (e.g., Debugger's RPP rule 11, Developer's Contract Enforcement rule 10) remain in their respective XMLs.
- **Empty MRP.xml**: If MRP.xml exists but is empty, `fetch_system_prompt()` should still succeed (append empty string) rather than raising an error. The file presence indicates intent, but zero-length content is a degenerate case.

## Key Unknowns
- [x] [Technical] MRP.xml location: Approved by user — alongside agent XMLs in `src/teddy_executor/resources/config/prompts/`.
- [ ] [Technical] `importlib.resources` API for loading MRP.xml: Need to verify the correct API call (`files()` vs `open_binary()`) for the prompts subdirectory to load MRP.xml from the same resource package. The existing `prompts.py` does NOT load from bundled resources (it only searches `.teddy/prompts/`), so PromptManager must load MRP.xml directly.

## Implementation Plan

### Overview
This slice has one technical unknown that should be de-risked by the Prototyper before the Developer begins. The core work is: (1) create MRP.xml with extracted shared content, (2) modify PromptManager to load and append it, and (3) remove the now-redundant content from agent XMLs.

### Detailed Tech Strategy

#### MRP.xml Loading
PromptManager's `fetch_system_prompt()` currently resolves agent XMLs via the filesystem hierarchy. For MRP.xml, it MUST load directly from the package using `importlib.resources`:
```python
import importlib.resources as resources

# In fetch_system_prompt, after resolving agent XML content:
mrp_xml_path = resources.files("teddy_executor.resources.config.prompts") / "MRP.xml"
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
`fetch_system_prompt()` must inject the agent name at the very start of the assembled system prompt, before the agent-specific XML and MRP content. The agent name is derived from the XML filename (e.g., `architect.xml` → "Agent Name: Architect"). The format is: `# Agent Name: {AgentName}\n\n` followed by the agent-specific XML content. The agent_name parameter already exists as a string input; it needs to be capitalized and formatted.

### Deliverables
- [ ] **Contract** - Create `src/teddy_executor/resources/config/prompts/MRP.xml` with extracted shared content: `<response_format>` block, shared `<general_rules>` (rules 1-9, Conflict Resolution, Programmatic Edits).
- [ ] **Harness** - Add test for MRP.xml loading in PromptManager (verify `fetch_system_prompt` assembled content contains MRP rules, verify FileNotFoundError is raised when MRP.xml is missing).
- [ ] **Logic** - Modify `PromptManager.fetch_system_prompt()` to: (1) inject agent name at start with "Agent Name: {CapitalizedAgentName}", (2) load MRP.xml via `importlib.resources`, (3) append MRP content after agent-specific XML.
- [ ] **Cleanup** - Remove shared `<general_rules>` and `<response_format>` blocks from all 6 agent XMLs. Keep agent-specific rules only.

### Key Unknown Resolution Strategy
Before the Developer starts, the Prototyper should verify:
1. `importlib.resources.files("teddy_executor.resources.config.prompts")` correctly resolves to the prompts directory.
2. `read_text(encoding="utf-8")` works on the Traversable returned by `files()`.
3. The FileNotFoundError scenario reproduces correctly when MRP.xml is absent.

The Prototyper spike lives at `spikes/prototypes/mrp-base-prompt/`.

## Verification
1. [ ] Run `pytest tests/suites/unit/core/services/test_prompt_manager.py -v` — all existing tests pass, new MRP injection tests pass.
2. [ ] Run full test suite: `pytest` — all tests pass (green-to-green).
3. [ ] Manual: `cat src/teddy_executor/resources/config/prompts/architect.xml | grep -c "<general_rules>"` — returns 0 (shared rules extracted).
4. [ ] Manual: `cat src/teddy_executor/resources/config/prompts/architect.xml | grep -c "<response_format>"` — returns 0 (response format extracted to MRP.xml).
5. [ ] Manual: `cat .teddy/prompts/architect.xml` — confirms MRP.xml NOT present in .teddy/prompts/.
6. [ ] Manual: `cat src/teddy_executor/resources/config/prompts/MRP.xml | grep -c "State Transition Protocol"` — returns at least 1 (MRP rules present).
7. [ ] Manual: `cat src/teddy_executor/resources/config/prompts/debugger.xml | grep -c "Remote Probing Protocol"` — returns at least 1 (agent-specific rule preserved).
8. [ ] Manual: Run a session with the developer agent and capture the system prompt. Verify it starts with "Agent Name: Developer" followed by the XML content.
9. [ ] Unit test: Verify that `fetch_system_prompt("architect", turn_path)` returns a string starting with "# Agent Name: Architect".
