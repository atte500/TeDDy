# Component Design: ContainerStub
- **Status:** Implemented
- **Classification:** Test Setup
- **Source:** [`tests/harness/setup/container_stub.py`](/tests/harness/setup/container_stub.py)

## Purpose
A punq-compatible container double for the session-loop wiring suites. It resolves a mapped service type to the exact instance the test supplied, falls back to a bare `Mock()` for an unmapped type, and records the constructor kwargs of every `resolve` call so a seed a boundary injects stays observable.

## Consumers
- The session-loop wiring suites (interrupt wiring, quit-listener wiring, resume-message threading), which each carried a byte-identical private copy before this stub was shared.
- [`test_session_loop_baseline_reset.py`](/tests/suites/unit/adapters/inbound/test_session_loop_baseline_reset.py): subclasses the stub so the guard is constructed from the injected baselines, which turns an otherwise invisible seed into an observable halt count.
- [`test_container_stub_harness.py`](/tests/suites/unit/test_container_stub_harness.py): the stub's own harness test.

## Dependencies
None — the double uses only `unittest.mock.Mock` from the standard library.

## Class Invariants
- `mapped_type_identity`: A mapped type resolves to the exact instance supplied, never a copy or a wrapper.
- `unmapped_type_fallback`: An unmapped type resolves to a bare `Mock()`, so a suite that omits a registration keeps running instead of failing on a lookup.
- `three_distinguishable_states`: A call with kwargs records those kwargs, a call without kwargs records an empty mapping, and a type never resolved records nothing, so a test can tell a bare resolve from an absent one.
- `recorded_kwargs_are_a_copy`: `resolved_kwargs` returns a copy of the recorded list, so a caller cannot mutate the double's history.
- `plain_class_over_dynamic_mock`: The double is a hand-written class with constructor-set state, never a dynamic mock, so its recorded history cannot be silently auto-created.

## Inbound Ports
None — this is a test double, not a port.

## Outbound Ports
None — nothing is injected; the mapping is supplied at construction.

## Data Contracts
- **`mapping`** (`dict[type, object]`, constructor): The service instances the double hands back, keyed by the port or service type production code resolves.
- **`resolved_kwargs(service_type)`** (`list[dict[str, object]]`): The constructor kwargs of each `resolve` call for that type, in call order.

## Operations

### `resolve(service_type, **kwargs) -> object`
- **Preconditions:** None; an absent mapping entry is a supported state.
- **Postconditions:** Records `kwargs` for `service_type` and returns the mapped instance, or a bare `Mock()` when the type is unmapped.
- **Exceptions:** None.

### `resolved_kwargs(service_type) -> list[dict[str, object]]`
- **Preconditions:** None; a type that was never resolved returns an empty list.
- **Postconditions:** Returns a copy of the recorded kwargs list, so the caller cannot mutate the double's history.
- **Exceptions:** None.
