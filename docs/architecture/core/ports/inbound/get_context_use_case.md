# Component Design: IGetContextUseCase
- **Status:** Implemented
- **Classification:** Core Inbound Port
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

### `get_context(context_files=None, include_tokens=True, agent_name="Unknown", total_window=0, current_turn=None, system_prompt_tokens=0, session_root=None, model=None) -> ProjectContext`
- **Preconditions:** None.
- **Postconditions:** Returns a `ProjectContext` carrying the repository tree, system details, and the content of the requested files. `context_files` maps a scope name to that scope's paths. A plain list stays accepted for backward compatibility and resolves as the `Default` scope. When `session_root` is supplied, a session-history path is classified as history only if it lives under that root; `None` keeps the session-agnostic default. The optional `model` is the effective model used for token counting; its `None` default keeps the port additively backward compatible.
- **Exceptions:** None declared by the port.
