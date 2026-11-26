# Component Design: LocalAgentCatalog
- **Status:** Planned
- **Source:** [`src/teddy_executor/adapters/outbound/local_agent_catalog.py`](/src/teddy_executor/adapters/outbound/local_agent_catalog.py)

## Purpose
Implements the `IAgentCatalog` outbound port by reporting which agent personas the current workspace declares. It delegates discovery to the same helper prompt resolution uses, so the roster a reviewer offers is exactly the set of personas the planner can load.

## Consumers
- [Composition Root](/src/teddy_executor/container.py): Registers `LocalAgentCatalog` against `IAgentCatalog` as a transient so no roster is cached across turns.
- [`TextualPlanReviewer`](../../adapters/inbound/textual_plan_reviewer.md): Receives the port, never this adapter, and therefore drives both a populated and an empty roster through an in-memory substitute.

## Dependencies
- **No injected ports.** The adapter reads the workspace through the existing `list_prompt_names()` helper in `src/teddy_executor/prompts.py`, which walks upward from the working directory to the first `.teddy/prompts/` it finds — the same directory `find_prompt_content` reads. Reusing that helper rather than re-implementing the scan is what makes the roster and the load path unable to diverge.
- **`canonical_agent_name`** (`src/teddy_executor/core/utils/string.py`): Normalizes each discovered stem to the casing the CLI uses for persona selection, so the reported name and the accepted name are the same string.

## Class Invariants
- `same_discovery_path_as_resolution`: The adapter lists the directory prompt resolution actually reads, so a name it reports always loads and a persona it omits cannot be loaded. It never reports a bundled persona that the workspace has not materialized, because resolution has no bundled fallback.
- `one_representation_per_persona`: Stems that differ only in case or extension collapse to one canonical name, mirroring `_search_prompt_in_dir`, which already treats `developer.md` and a stale `developer.xml` as one persona.
- `stable_order`: Repeated calls return the same ascending order within one process, because a roster that reorders between openings is unusable from the keyboard.
- `empty_is_not_failure`: A missing prompts directory yields an empty tuple, never an error, because a fresh workspace legitimately declares no personas.
- `failure_propagation`: A listing failure is translated into `AgentCatalogError` and never swallowed into an empty tuple, because "no personas installed" and "could not read the directory" are different facts.

## Inbound Ports
None — this is an outbound adapter.

## Outbound Ports
- **`IAgentCatalog`**: The driven contract implemented by this adapter. See the [IAgentCatalog design](../../core/ports/outbound/agent_catalog.md).

## Data Contracts
- **`list_agents()` result**: a `tuple[str, ...]` of canonical, de-duplicated persona names in ascending order. An empty tuple means the workspace declares no personas.
- **`AgentCatalogError`**: raised when the prompts directory exists but cannot be listed, translated from the underlying filesystem failure. Inherits from `TeddyError`, so the reviewer reports it as a user-facing failure instead of crashing the TUI.

## Operations

### `list_agents() -> tuple[str, ...]`
- **Preconditions:** None. Safe to call before any session exists and from a read-only workspace.
- **Postconditions:** Returns every declared persona exactly once, canonically cased, in ascending order. Returns an empty tuple when no prompts directory is found or it holds no file.
- **Exceptions:**
  - `AgentCatalogError`: the prompts directory exists but its entries cannot be listed.
