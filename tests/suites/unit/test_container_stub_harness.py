"""Harness tests: the shared punq-compatible container stub.

The session-loop wiring suites each carried a hand-rolled, byte-identical
``_ContainerStub`` (interrupt wiring, quit-listener wiring, resume-message
threading). The shared ``ContainerStub`` retires all three copies: a punq
``resolve``-compatible double that returns the mapped service for a known type
and a bare ``Mock()`` fallback for unmapped types.

It also records the constructor kwargs of every ``resolve`` call, because punq
injects them into the constructed service and a boundary that seeds one (a
guard's baselines, for instance) is otherwise unobservable.

Mirrors the established harness-double convention (``FakeHTTPResponse``,
``FakeRegistryCache``, ``FakeQuitKeyListener``): a plain class with
constructor-set state.
"""

from unittest.mock import Mock

from tests.harness.setup.container_stub import ContainerStub


def test_resolves_a_mapped_type_to_the_exact_service():
    """A mapped type must resolve to the EXACT service instance injected."""
    mapped = object()
    stub = ContainerStub({int: mapped})

    assert stub.resolve(int) is mapped


def test_returns_a_mock_fallback_for_an_unmapped_type():
    """An unmapped type must fall back to a bare Mock() instance."""
    stub = ContainerStub({})

    resolved = stub.resolve(str)

    assert isinstance(resolved, Mock)


def test_records_the_constructor_kwargs_of_every_resolve_call():
    """Every resolve records the constructor kwargs it received, in call order.

    A boundary seeds a service by passing constructor kwargs through
    ``resolve``, so that seed is only assertable when the double keeps it. A
    call without kwargs records an empty mapping, and a type never resolved
    records nothing at all, so the two cases stay distinguishable.
    """
    stub = ContainerStub({})

    stub.resolve(int, initial_turn=0, initial_cost=2.0)
    stub.resolve(str)
    stub.resolve(int, initial_turn=3)

    assert stub.resolved_kwargs(int) == [
        {"initial_turn": 0, "initial_cost": 2.0},
        {"initial_turn": 3},
    ]
    assert stub.resolved_kwargs(str) == [{}]
    assert stub.resolved_kwargs(float) == []
