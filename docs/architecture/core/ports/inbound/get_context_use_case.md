# Component Design: IGetContextUseCase
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/ports/inbound/get_context_use_case.py`](/src/teddy_executor/core/ports/inbound/get_context_use_case.py)

## Purpose
Defines the inbound port for gathering aggregated project context. It is the primary entry point that produces the structured `ProjectContext` payload for planning and display. The port is implemented by the `ContextService`.

## Consumers
- [CLI Adapter](../../../adapters/inbound/cli.md): Invokes context gathering for the `context` command and for session startup.

## Dependencies
- **`ProjectContext`** (`teddy_executor.core.domain.models`): The return type of the use case.

## Class Invariants
- `stateless_contract`: The port declares behavior only; implementations gather context without mutating the workspace beyond creating a missing `.teddy/init.context`.

## Inbound Ports
- **`IGetContextUseCase`**: Exposes the single `get_context(...)` operation.

## Outbound Ports
None — the port declares no injected dependencies; the implementing service owns its own outbound ports.

## Data Contracts
- **`ProjectContext`** (dataclass): The returned aggregate. See the [ProjectContext design](../../domain/project_context.md).

## Operations

### `get_context(context_files=None, include_tokens=True, agent_name="Unknown", total_window=0, cache_dir=None, current_turn=None, system_prompt_tokens=0) -> ProjectContext`
- **Preconditions:** None.
- **Postconditions:** Returns a `ProjectContext` carrying the repository tree, system details, and the content of the requested files.
- **Exceptions:** None declared by the port.
