# Component Design: ContextScenarios (Setup)
- **Status:** Implemented
- **Classification:** Test Setup
- **Source:** [`tests/harness/setup/context_scenarios.py`](/tests/harness/setup/context_scenarios.py)

## Purpose
Supplies the canonical context-payload scenarios a context-service test needs to drive every branch of the session-resources partition without creating real session directories. Data only: it imports no context-service code, so a test cannot couple to the implementation it exercises.

## Consumers
- [`test_context_scenarios_harness.py`](/tests/suites/unit/test_context_scenarios_harness.py): pins the scenario contract and the partition branch each canonical path drives.
- Context-service tests (`tests/suites/unit/core/services/test_context_service.py`): splat `MIXED_SCOPES.get_context_kwargs()` to assemble a payload carrying one session-scoped non-history path, one session-scoped own-history path, and one turn-scoped path, and are the intended reader of `COSTED_SESSION.get_context_kwargs()` for the reviewer-row cases.

## Dependencies
None. Standard library only (`collections.abc.Sequence`, `typing.NamedTuple`).

## Class Invariants
- `ContextScenario.context_files` always carries both session-mode scope keys, `Session` and `Turn`. An empty scenario holds empty lists rather than an empty mapping, because a falsy mapping makes the context service fall back to the default vault paths.
- Scope lists preserve declaration order and are never sorted, because `session.context` line order is the user's knob.
- `ContextScenario.file_contents` holds exactly one deterministic body per distinct path.
- `ContextScenario.get_context_kwargs()` forwards every `get_context` keyword the scenario carries — the scope mapping, `session_root`, and the two reviewer rows — so a service test never hand-assembles the dict, and widening the seam needs no consumer edit.
- `model` and `session_cost` are trailing defaults of `None`, read as "no model resolved, no cost recorded", which are the seam's own defaults.
- `COSTED_SESSION` derives its path lists from `MIXED_SCOPES` instead of restating them, so the partition payload and the costed payload cannot drift.

## Inbound Ports
None. The module exposes data and builders:
- `SESSION_ROOT`, `SESSION_DOCUMENT`, `OWN_HISTORY_REQUEST`, `TURN_DOCUMENT`: canonical path constants.
- `MIXED_SCOPES`, `COSTED_SESSION`, `EXPORT_SCOPES`: the canonical bundles — the partition payload, that payload plus a resolved model and a recorded cost, and that payload with no session root.
- `context_scenario(session=None, turn=None, session_root=SESSION_ROOT, model=None, session_cost=None) -> ContextScenario`.
- `content_for(path) -> str`.

## Outbound Ports
None. The module reads no port.

## Data Contracts
- **`ContextScenario`**: a `NamedTuple` carrying `context_files: dict[str, list[str]]`, `file_contents: dict[str, str]`, `session_root: str | None`, and the two reviewer rows `model: str | None` and `session_cost: float | None`, both defaulting to `None`.

## Operations

### `context_scenario(session=None, turn=None, session_root=SESSION_ROOT, model=None, session_cost=None) -> ContextScenario`
- **Preconditions:** None.
- **Postconditions:** the returned scenario carries both scope keys, preserves the given order, maps each distinct path to `content_for(path)`, and carries `model` and `session_cost` verbatim so `get_context_kwargs()` forwards them.
- **Exceptions:** None.

### `content_for(path) -> str`
- **Preconditions:** None.
- **Postconditions:** returns a deterministic body naming `path`, so two paths never share content.
- **Exceptions:** None.
