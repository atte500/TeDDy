# Component Design: Sigint Delivery
- **Status:** Implemented
- **Classification:** Test Setup
- **Source:** [`tests/harness/setup/sigint_delivery.py`](/tests/harness/setup/sigint_delivery.py)

## Purpose
Observes SIGINT delivery in-process without raising `KeyboardInterrupt` in the test process, and — in routing mode — drives whichever handler the run installed at press time, so an acceptance test exercises the real interrupt lifecycle instead of a stand-in. Patching whichever primitive the platform exposes keeps the observation valid when the production delivery primitive changes.

## Consumers
- [`test_execute_interrupt.py`](/tests/suites/acceptance/test_execute_interrupt.py): Uses `ROUTE_TO_HANDLER` so a press fired from inside the fake shell reaches the real `InterruptGuard` while the orchestrator holds its EXECUTING phase, producing a report to assert on rather than an escaped abort.
- **Delivery-order suites**: Use the default `RECORD` mode, which observes the press and leaves the ambient handler untouched.

## Dependencies
- **`signal` (standard library)**: `stub_sigint_delivery` patches `signal.raise_signal` and, where the platform exposes it, `signal.pthread_kill`; routing mode reads the live disposition through `signal.getsignal`.

## Class Invariants
- `record_before_route`: The delivered signal number is recorded before the handler is invoked, so a handler that raises — the guard's WAITING branch does exactly that — still leaves evidence of the press.
- `disposition_resolved_at_press_time`: Routing reads the installed disposition when the press fires, never when the stub is applied, because the run installs its handler after the stub.
- `non_callable_disposition_skipped`: A disposition such as `SIG_IGN` is not a Python callable and is skipped rather than invoked.
- `record_mode_leaves_the_handler_untouched`: Only `ROUTE_TO_HANDLER` invokes anything, so a suite asserting delivery order keeps the ambient disposition intact.

## Inbound Ports
None — a harness helper consumed directly by tests.

## Outbound Ports
None declared.

## Data Contracts
- **`SigintDeliveryMode`** (`Enum`): `RECORD` records and stops; `ROUTE_TO_HANDLER` also invokes the handler installed at press time. An enum rather than a boolean, so a third mode cannot silently be read as one of the two.
- **`DeliveredSignals`** (`list[int]`): The per-test recorder of delivered signal numbers returned to the caller.

## Operations

### `stub_sigint_delivery(monkeypatch, mode=SigintDeliveryMode.RECORD) -> DeliveredSignals`
- **Preconditions:** `monkeypatch` is the active pytest fixture, so every patch unwinds with the test.
- **Postconditions:** `signal.raise_signal` is patched to record each delivered number; `signal.pthread_kill` is patched only where the attribute exists, because Windows lacks it and the test process must never receive a real signal. In routing mode the recorded press also invokes the callable SIGINT disposition installed at that moment. Returns the recorder list.
