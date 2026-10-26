<!--
Destination: docs/architecture/{boundary}/{layer}/{type}/{component-name}.md
-->

# Component Design: {{Component Name}}
- **Status:** [Planned | Implemented | Refactoring]
- **Source:** [`src/path/to/file.ext`](/src/path/to/file.ext)

## Purpose
1-2 sentences summarizing the core responsibility and boundary role of this component.

## Consumers
Upstream callers, controllers, or services that depend on or invoke this component:
- [`CallerComponent`](./path/to/caller.md): Invokes this component to execute [workflow/operation].

## Dependencies
Downstream components, outbound ports, or external libraries required by this component:
- [`DependencyComponent`](./path/to/dependency.md): Injected via constructor to fulfill [outbound operation].

## Class Invariants
Conditions that must hold true throughout the component lifecycle. If stateless, state: `None — stateless component.`
- `invariant_statement`: description of condition.

## Inbound Ports
Use-case interfaces or API signatures this component exposes to consumers:
- **`PortName`**: Signature and operations provided.

## Outbound Ports
Dependency contracts this component requires injected:
- **`PortName`**: Signature and operations consumed.

## Data Contracts
Data transfer objects, schemas, payloads, or immutable models managed or exchanged by this component:
- **`DtoOrPayloadName`**: Structure, fields, types, and constraints.

## Operations
Public method specifications. Avoid pseudocode; specify signatures, preconditions, postconditions, and error modes:

### `method_name(args) -> ReturnType`
- **Preconditions:** What must hold before calling (validated via guard clauses or runtime assertions).
- **Postconditions:** What is guaranteed upon successful return.
- **Exceptions:** Specific exceptions raised when preconditions or operations fail (never generic or swallowed errors).
