# Component Design: IAgentCatalog
- **Status:** Planned
- **Classification:** Core Outbound Port
- **Source:** [`src/teddy_executor/core/ports/outbound/agent_catalog.py`](/src/teddy_executor/core/ports/outbound/agent_catalog.py)

## Purpose
Declares the outbound contract for discovering which agent personas a workspace offers, so the reviewer can present a roster without importing the filesystem-scanning prompt module and tests can substitute an in-memory list.

## Consumers
- [`TextualPlanReviewer`](/docs/architecture/adapters/inbound/textual_plan_reviewer.md): Invokes this port to populate the agent-switch modal reached by pressing `e` on the System context node, and to mark which roster entry is the active persona.

## Dependencies
None. A port declares a contract and therefore depends on nothing; implementations supply the discovery mechanism. The local implementation reads `.teddy/prompts/` and delegates the directory scan to the existing `list_prompt_names()` helper in `src/teddy_executor/prompts.py`, so prompt-name discovery keeps exactly one implementation.

## Class Invariants
- `stable_order`: repeated calls return the same ordering within one process, because a roster whose entries reorder between openings is unusable from the keyboard.
- `no_bundled_fallback`: the port reports only what the workspace currently declares, because prompt resolution reads `.teddy/prompts/` alone and a fabricated roster would offer personas the planner cannot load.

## Inbound Ports
None. This is an outbound contract consumed by adapters and services, not an interface exposed to consumers.

## Outbound Ports
None. The port itself declares no downstream dependencies.

## Data Contracts
- **`list_agents()` result**: a `tuple[str, ...]` of canonical persona names in ascending order, with duplicates removed. An empty tuple means the workspace declares no personas; it never means discovery failed.
- **`AgentCatalogError`**: raised when the prompts directory exists but cannot be read (a permissions or I/O failure). Inherits from `TeddyError`, so the reviewer reports it as a user-facing failure instead of crashing the TUI. A missing directory is not an error and yields an empty tuple.

## Operations

### `list_agents() -> tuple[str, ...]`
- **Preconditions:** None. The operation is safe to call before any session exists and from a read-only workspace.
- **Postconditions:** Returns every declared persona name exactly once, canonically cased, in ascending order. Returns an empty tuple when no prompts directory exists or it holds no prompt file.
- **Exceptions:**
  - `AgentCatalogError`: the prompts directory exists but its entries cannot be listed. Translated by the local adapter from the underlying filesystem failure so no raw `OSError` crosses the boundary.
