# Component Design: ContextScenarios (Setup)
- **Status:** Implemented
- **Classification:** Test Setup
- **Source:** [`tests/harness/setup/context_scenarios.py`](/tests/harness/setup/context_scenarios.py)

## Purpose
Supplies the canonical context-payload scenarios a context-service test needs to drive every branch of the session-resources partition without creating real session directories. Data only: it imports no context-service code, so a test cannot couple to the implementation it exercises.

## Consumers
- [`test_context_scenarios_harness.py`](/tests/suites/unit/test_context_scenarios_harness.py): pins the scenario contract and the partition branch each canonical path drives.
- Context-service tests (`tests/suites/unit/core/services/test_context_service.py`): the intended consumer for the Wiring and Core deliverables, reading `MIXED_SCOPES.get_context_kwargs()` to assemble a payload carrying one session-scoped non-history path, one session-scoped own-history path, and one turn-scoped path.

## Dependencies
None. Standard library only (`collections.abc.Sequence`, `typing.NamedTuple`).

## Class Invariants
- `ContextScenario.context_files` always carries both session-mode scope keys, `Session` and `Turn`. An empty scenario holds empty lists rather than an empty mapping, because a falsy mapping makes the context service fall back to the default vault paths.
- Scope lists preserve declaration order and are never sorted, because `session.context` line order is the user's knob.
- `ContextScenario.file_contents` holds exactly one deterministic body per distinct path.
- `ContextScenario.get_context_kwargs()` forwards the scope mapping together with `session_root`.

## Inbound Ports
None. The module exposes data and builders:
- `SESSION_ROOT`, `SESSION_DOCUMENT`, `OWN_HISTORY_REQUEST`, `TURN_DOCUMENT`: canonical path constants.
- `MIXED_SCOPES`: the canonical `ContextScenario`.
- `context_scenario(session=None, turn=None, session_root=SESSION_ROOT) -> ContextScenario`.
- `content_for(path) -> str`.

## Outbound Ports
None. The module reads no port.

## Data Contracts
- **`ContextScenario`**: a `NamedTuple` carrying `context_files: dict[str, list[str]]`, `file_contents: dict[str, str]`, and `session_root: str`.

## Operations

### `context_scenario(session=None, turn=None, session_root=SESSION_ROOT) -> ContextScenario`
- **Preconditions:** None.
- **Postconditions:** the returned scenario carries both scope keys, preserves the given order, and maps each distinct path to `content_for(path)`.
- **Exceptions:** None.

### `content_for(path) -> str`
- **Preconditions:** None.
- **Postconditions:** returns a deterministic body naming `path`, so two paths never share content.
- **Exceptions:** None.
