# Component Design: IPlanParser
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/ports/inbound/plan_parser.py`](/src/teddy_executor/core/ports/inbound/plan_parser.py)

## Purpose
Defines the inbound port for parsing a raw plan string into a structured `Plan` domain object. It decouples the execution orchestrator from any specific plan format so alternative parsers can be swapped in. The port is implemented by the `MarkdownPlanParser`.

## Consumers
- [`ExecutionOrchestrator`](../../services/execution_orchestrator.md): Parses raw plan content before executing an approved plan.

## Dependencies
- **`Plan`** (`teddy_executor.core.domain.models`): The return type of the parse operation.

## Class Invariants
- `abstract_base_class`: The port is an `ABC`; implementations must override `parse`.

## Inbound Ports
- **`IPlanParser`**: Exposes the single `parse(...)` operation.

## Outbound Ports
None — the port declares no injected dependencies.

## Data Contracts
- **`Plan`** (`teddy_executor.core.domain.models`): The parsed domain object.
- **`InvalidPlanError`** (`Exception`): Carries `offending_nodes` and `validation_errors`, and exposes `offending_node` for backward compatibility.

## Operations

### `parse(plan_content, plan_path=None) -> Plan`
- **Preconditions:** `plan_content` is a non-empty string.
- **Postconditions:** Returns a valid `Plan`.
- **Exceptions:** `InvalidPlanError` when the content is malformed for the parser's format.
